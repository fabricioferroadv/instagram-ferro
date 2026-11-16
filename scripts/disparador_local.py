"""Disparador do notebook — cobre as falhas do relógio do GitHub.

O agendamento do GitHub ("a cada 15 min") às vezes passa horas sem rodar
(16/11/2026: nenhuma execução das 8h58 às 12h). Este script roda no Windows a
cada 15 min e, SÓ quando consegue confirmar que há post vencido esperando,
aciona o publicador ("Run workflow").

Regra de ouro: na dúvida, NÃO dispara.
  - não conseguiu ler a fila no GitHub          → não dispara
  - não conseguiu ver as execuções do publicador → não dispara
  - já tem execução rodando ou na fila           → não dispara (ela resolve)
  - nenhum post vencido                          → não dispara

Mesmo disparado, o publicador ainda confere no próprio Instagram (pela legenda)
se o post já saiu antes de publicar — e não publica se não conseguir conferir.

Roda escondido (pythonw) pela tarefa "Ferro - Disparador do publicador".
Registro em disparador.log, nesta mesma pasta de scripts (fora do Git).
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG = Path(__file__).resolve().parent / "disparador.log"
REPO = "fabricioferroadv/instagram-ferro"
WORKFLOW = "publicar.yml"
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
BRT = timezone(timedelta(hours=-3))


def log(msg):
    linha = f"{datetime.now(BRT):%d/%m/%Y %H:%M:%S}  {msg}"
    try:
        # mantém o arquivo pequeno: últimas ~2000 linhas
        antigas = LOG.read_text(encoding="utf-8").splitlines()[-2000:] if LOG.exists() else []
        LOG.write_text("\n".join(antigas + [linha]) + "\n", encoding="utf-8")
    except OSError:
        pass
    print(linha)


def roda(*cmd):
    r = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=90, creationflags=SEM_JANELA)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])}…: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def posts_vencidos():
    """Lê a fila direto do GitHub (origin/main), sem mexer na pasta local."""
    roda("git", "fetch", "--quiet", "origin", "main")
    nomes = roda("git", "ls-tree", "--name-only", "origin/main", "fila/").split()
    agora = datetime.now(timezone.utc)
    vencidos = []
    for nome in nomes:
        if not nome.endswith(".json"):
            continue
        post = json.loads(roda("git", "show", f"origin/main:{nome}").lstrip("﻿"))
        quando = datetime.fromisoformat(post["publicar_em"])
        if quando <= agora:
            vencidos.append((quando, Path(nome).stem, agora - quando))
    presos = [n for n in roda("git", "ls-tree", "--name-only", "origin/main", "publicando/").split()
              if n.endswith(".json")]
    return sorted(vencidos), presos


def execucao_ativa():
    saida = roda("gh", "run", "list", "-R", REPO, "--workflow", WORKFLOW, "-L", "10",
                 "--json", "status,createdAt,event")
    return [r for r in json.loads(saida) if r["status"] != "completed"]


def main():
    simular = "--simular" in sys.argv          # mostra o que faria, sem disparar
    try:
        vencidos, presos = posts_vencidos()
    except Exception as e:
        log(f"NÃO DISPAREI — não consegui ler a fila no GitHub ({e})")
        return 0
    if not vencidos and not presos:
        return 0                                    # silencioso: nada a fazer

    descr = ", ".join(f"{nome} (atraso {int(atraso.total_seconds() // 60)} min)"
                      for _, nome, atraso in vencidos)
    if presos:
        descr += ("; " if descr else "") + "preso em publicando: " + ", ".join(presos)

    try:
        ativas = execucao_ativa()
    except Exception as e:
        log(f"NÃO DISPAREI — não consegui ver as execuções do publicador ({e}). Pendentes: {descr}")
        return 0
    if ativas:
        log(f"Não disparei — já há execução {ativas[0]['status']} ({ativas[0]['event']}). Pendentes: {descr}")
        return 0

    if simular:
        print(f"[simulação] dispararia o publicador. Pendentes: {descr}")
        return 0
    try:
        roda("gh", "workflow", "run", WORKFLOW, "-R", REPO)
    except Exception as e:
        log(f"FALHOU ao disparar ({e}). Pendentes: {descr}")
        return 1
    log(f"DISPAREI o publicador. Pendentes: {descr}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
