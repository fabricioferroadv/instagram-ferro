"""Fila de publicação — roda no SEU computador.

Exemplos:
    python fila.py agendar 5-documentos-acidente-trabalho --quando "05/11/2026 19:00"
    python fila.py agendar 5-documentos-acidente-trabalho --quando "05/11/2026 19:00" --enviar
    python fila.py listar
    python fila.py cancelar 20261105-1900-5-documentos-acidente-trabalho --enviar
    python fila.py reagendar 20261105-1900-5-documentos-acidente-trabalho --quando "06/11/2026 12:00" --enviar
    python fila.py enviar

Sem --enviar, só prepara aqui (nada vai para o GitHub). Com --enviar, envia e
o GitHub publica sozinho no horário, com o computador ligado ou não.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "scripts"))
import regras  # noqa: E402

PRONTOS = RAIZ.parent / "PRONTOS PARA PUBLICAR"
FILA, PUBLICADOS, ERROS, MIDIA = (RAIZ / p for p in ("fila", "publicados", "erros", "midia"))
BRT = timezone(timedelta(hours=-3))   # Brasil sem horário de verão desde 2019


# ---------------------------------------------------------------- utilidades

def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=RAIZ, check=check, capture_output=True, text=True)


def tem_remoto():
    return bool(git("remote", check=False).stdout.strip())


def sincroniza():
    """Traz o estado da nuvem (o GitHub move os arquivos ao publicar)."""
    if tem_remoto():
        r = git("pull", "--rebase", "--autostash", "--quiet", check=False)
        if r.returncode != 0:
            sys.exit(f"Não consegui atualizar do GitHub:\n{r.stderr}")


def envia(mensagem):
    if not tem_remoto():
        print("\n(GitHub ainda não conectado — ficou preparado só aqui. Ver README, passo 3.)")
        return
    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("Nada novo para enviar.")
        return
    git("commit", "-m", mensagem)
    r = git("push", check=False)
    if r.returncode != 0:
        sys.exit(f"Falhou o envio ao GitHub:\n{r.stderr}")
    print("Enviado ao GitHub. ✔")


def le_quando(texto):
    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %Hh%M", "%d/%m/%Y %Hh"):
        try:
            return datetime.strptime(texto.strip(), fmt).replace(tzinfo=BRT)
        except ValueError:
            pass
    sys.exit(f'Data não entendida: "{texto}". Use, por exemplo: "05/11/2026 19:00"')


def recusa_passado(quando):
    if quando < datetime.now(BRT) + timedelta(minutes=2):
        sys.exit(f"Recusado: {quando:%d/%m/%Y %H:%M} já passou (ou é daqui a menos de 2 min).")


def slug(texto):
    import unicodedata
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60]


def confere_imagens(arquivos):
    erros = []
    try:
        from PIL import Image
    except ImportError:
        print("Aviso: Pillow não instalado — pulei a conferência de tamanho/proporção.")
        Image = None
    for a in arquivos:
        if a.stat().st_size > regras.MAX_BYTES_IMAGEM:
            erros.append(f"{a.name}: maior que 8 MB")
        if Image:
            with Image.open(a) as im:
                if im.format != "JPEG":
                    erros.append(f"{a.name}: não é JPEG de verdade ({im.format})")
                prop = im.width / im.height
                if not (0.8 - 0.01 <= prop <= 1.91 + 0.01):
                    erros.append(f"{a.name}: proporção {im.width}x{im.height} fora de 4:5 a 1,91:1")
    return erros


def acha(id_post):
    for pasta in (FILA, ERROS):
        arq = pasta / f"{id_post}.json"
        if arq.exists():
            return arq
    sys.exit(f"Não achei '{id_post}' na fila nem nos erros. Use: python fila.py listar")


# ---------------------------------------------------------------- comandos

def cmd_agendar(a):
    sincroniza()
    origem = Path(a.pasta)
    if not origem.is_dir():
        origem = PRONTOS / a.pasta
    if not origem.is_dir():
        sys.exit(f"Pasta não encontrada: {a.pasta}\n(procurei também em {PRONTOS})")

    imagens = sorted(p for p in origem.iterdir()
                     if re.fullmatch(r"\d{2}\.jpe?g", p.name, re.IGNORECASE))
    leg = origem / "legenda.txt"
    if not leg.exists():
        sys.exit(f"Falta legenda.txt em {origem}")
    legenda = leg.read_text(encoding="utf-8-sig").strip()

    quando = le_quando(a.quando)
    recusa_passado(quando)
    id_post = f"{quando:%Y%m%d-%H%M}-{slug(origem.name)}"
    if (FILA / f"{id_post}.json").exists() or (PUBLICADOS / f"{id_post}.json").exists():
        sys.exit(f"Já existe um post com o id {id_post}.")

    post = {
        "id": id_post,
        "titulo": a.titulo or origem.name,
        "publicar_em": quando.isoformat(timespec="minutes"),
        "imagens": [f"midia/{id_post}/{p.name.lower().replace('.jpeg', '.jpg')}" for p in imagens],
        "legenda": legenda,
        "termos_liberados": a.liberar or [],
        "aprovado_em": datetime.now(BRT).isoformat(timespec="minutes"),
        "origem": origem.name,
        "status": "agendado",
    }

    erros = regras.problemas_post(post) + confere_imagens(imagens)
    if erros:
        print("NÃO AGENDADO — corrija antes:")
        for e in erros:
            print(f"  - {e}")
        if any("OAB" in e for e in erros):
            print('\nSe tiver certeza de que o uso é informativo, repita com --liberar "termo".')
        sys.exit(1)

    destino = MIDIA / id_post
    destino.mkdir(parents=True, exist_ok=True)
    for p, rel in zip(imagens, post["imagens"]):
        shutil.copy2(p, RAIZ / rel)
    FILA.mkdir(exist_ok=True)
    (FILA / f"{id_post}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print(f"Agendado: {post['titulo']}")
    print(f"  quando:  {quando:%d/%m/%Y %H:%M} (horário de Brasília)")
    print(f"  imagens: {len(imagens)}  |  legenda: {len(legenda)} caracteres")
    print(f"  id:      {id_post}")
    print("  obs.:    o GitHub confere a fila periodicamente — pode sair até ~1 h depois.")
    if a.enviar:
        envia(f"Agendar: {id_post}")


def cmd_listar(a):
    sincroniza()
    for titulo, pasta in (("NA FILA", FILA), ("COM ERRO", ERROS), ("PUBLICADOS (últimos 10)", PUBLICADOS)):
        arquivos = sorted(pasta.glob("*.json"))
        if titulo.startswith("PUBLICADOS"):
            arquivos = arquivos[-10:]
        print(f"\n{titulo}: {len(arquivos)}")
        for arq in arquivos:
            p = json.loads(arq.read_text(encoding="utf-8-sig"))
            q = datetime.fromisoformat(p["publicar_em"]).astimezone(BRT)
            extra = p.get("link") or p.get("detalhe") or ""
            print(f"  {q:%d/%m %H:%M}  {p['id']}  {extra}")


def cmd_cancelar(a):
    sincroniza()
    arq = acha(a.id)
    post = json.loads(arq.read_text(encoding="utf-8-sig"))
    arq.unlink()
    shutil.rmtree(MIDIA / post["id"], ignore_errors=True)
    print(f"Cancelado: {post['id']}")
    if a.enviar:
        envia(f"Cancelar: {post['id']}")


def cmd_reagendar(a):
    sincroniza()
    arq = acha(a.id)
    post = json.loads(arq.read_text(encoding="utf-8-sig"))
    if "CONFIRA no Instagram" in post.get("detalhe", "") and not a.ja_conferi:
        sys.exit("Este post caiu no meio do envio. Confira no Instagram se ele saiu.\n"
                 "Se NÃO saiu, repita o comando com --ja-conferi.")
    quando = le_quando(a.quando)
    recusa_passado(quando)
    post["publicar_em"] = quando.isoformat(timespec="minutes")
    post["status"] = "agendado"
    post.pop("detalhe", None)
    arq.unlink()
    (FILA / f"{post['id']}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    print(f"Reagendado: {post['id']} para {quando:%d/%m/%Y %H:%M}")
    if a.enviar:
        envia(f"Reagendar: {post['id']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Fila de publicação do Instagram (Ferro Advocacia)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("agendar", help="coloca um post aprovado na fila")
    s.add_argument("pasta", help="nome da pasta em PRONTOS PARA PUBLICAR (ou caminho)")
    s.add_argument("--quando", required=True, help='ex.: "05/11/2026 19:00"')
    s.add_argument("--titulo")
    s.add_argument("--liberar", action="append", metavar="TERMO",
                   help="libera conscientemente um termo barrado pela regra da OAB")
    s.add_argument("--enviar", action="store_true", help="envia ao GitHub")
    s.set_defaults(f=cmd_agendar)

    s = sub.add_parser("listar", help="mostra fila, erros e publicados")
    s.set_defaults(f=cmd_listar)

    s = sub.add_parser("cancelar", help="tira um post da fila")
    s.add_argument("id")
    s.add_argument("--enviar", action="store_true")
    s.set_defaults(f=cmd_cancelar)

    s = sub.add_parser("reagendar", help="muda o horário (ou recoloca um post com erro)")
    s.add_argument("id")
    s.add_argument("--quando", required=True)
    s.add_argument("--ja-conferi", action="store_true")
    s.add_argument("--enviar", action="store_true")
    s.set_defaults(f=cmd_reagendar)

    s = sub.add_parser("enviar", help="envia ao GitHub o que foi preparado")
    s.set_defaults(f=lambda a: (sincroniza(), envia("Atualizar fila")))

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
