"""Publica no Instagram os posts da fila cujo horário chegou.

Roda no GitHub Actions a cada 15 minutos. Só biblioteca padrão do Python.

Estados (cada estado é uma pasta do repositório):
    fila/        aprovado, esperando o horário
    publicando/  enviando agora — se um arquivo ficar aqui, a execução caiu no
                 meio: CONFIRA no Instagram antes de reenviar
    publicados/  saiu (com id e link do post)
    erros/       não saiu (com o motivo)

Variáveis de ambiente:
    IG_ACCESS_TOKEN  (secret)  token de Página da Meta
    IG_ACCOUNT_ID    (variable) id da conta Instagram Business
    GRAPH_VERSION    opcional, padrão v26.0
    SIMULAR=1        não chama a Meta nem faz git push (teste local)
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import regras  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FILA, PUBLICANDO, PUBLICADOS, ERROS = (RAIZ / p for p in ("fila", "publicando", "publicados", "erros"))
TOLERANCIA_ATRASO = timedelta(hours=3)   # passou disso, segura o post (não publica fora de hora)
SIMULAR = os.environ.get("SIMULAR") == "1"
GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v26.0')}"
BRT = timezone(timedelta(hours=-3))


class ErroMeta(Exception):
    pass


# ---------------------------------------------------------------- git

def git(*args):
    if SIMULAR:
        print(f"   [simulação] git {' '.join(args)}")
        return
    subprocess.run(["git", *args], cwd=RAIZ, check=True)


def salva_estado(mensagem):
    git("add", "-A", "fila", "publicando", "publicados", "erros")
    if not SIMULAR:
        mudou = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=RAIZ).returncode != 0
        if not mudou:
            return
    git("commit", "-m", mensagem)
    git("pull", "--rebase", "--quiet")   # caso você tenha agendado algo nesse meio-tempo
    git("push")


def move(arquivo: Path, destino: Path, post: dict) -> Path:
    destino.mkdir(exist_ok=True)
    novo = destino / arquivo.name
    novo.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    if arquivo != novo:
        arquivo.unlink()
    return novo


# ---------------------------------------------------------------- Meta

def _chamada(metodo, caminho, dados=None):
    dados = dict(dados or {})
    dados["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    corpo = urllib.parse.urlencode(dados).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{GRAPH}/{caminho}?{corpo.decode()}")
    else:
        req = urllib.request.Request(f"{GRAPH}/{caminho}", data=corpo, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            erro = json.load(e).get("error", {})
            msg = erro.get("error_user_msg") or erro.get("message") or str(e)
        except Exception:
            msg = str(e)
        raise ErroMeta(f"Meta recusou ({e.code}): {msg}") from None


def espera_pronto(container_id, tentativas=30, intervalo=3):
    for _ in range(tentativas):
        r = _chamada("GET", container_id, {"fields": "status_code,status"})
        codigo = r.get("status_code")
        if codigo == "FINISHED":
            return
        if codigo in ("ERROR", "EXPIRED"):
            raise ErroMeta(f"container {codigo}: {r.get('status', 'sem detalhe')}")
        time.sleep(intervalo)
    raise ErroMeta("a Meta não terminou de processar a imagem a tempo")


def url_publica(caminho_relativo):
    repo = os.environ.get("GITHUB_REPOSITORY", "USUARIO/REPOSITORIO")
    ramo = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{ramo}/{urllib.parse.quote(caminho_relativo)}"


def confere_url(url, video=False):
    """A Meta só baixa se a URL for pública e do tipo certo. Testa antes."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tipo = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise ErroMeta(f"arquivo não está público ({e.code}): {url}") from None
    # o GitHub serve .mp4 como application/octet-stream — a Meta aceita (testado em 05/11/2026)
    ok = tipo.startswith(("video/", "application/octet-stream")) if video else tipo.startswith("image/")
    if not ok:
        raise ErroMeta(f"URL não devolve {'vídeo' if video else 'imagem'} (Content-Type: {tipo}): {url}")


def publica_reel(post: dict) -> dict:
    conta = os.environ["IG_ACCOUNT_ID"]
    video = url_publica(post["video"])
    capa = url_publica(post["capa"]) if post.get("capa") else ""
    if SIMULAR:
        print(f"   [simulação] publicaria o Reel: {video}" + (f"\n      capa: {capa}" if capa else ""))
        return {"id": "SIMULADO", "permalink": ""}
    confere_url(video, video=True)
    dados = {"media_type": "REELS", "video_url": video, "caption": post["legenda"], "share_to_feed": "true"}
    if capa:
        confere_url(capa)
        dados["cover_url"] = capa
    r = _chamada("POST", f"{conta}/media", dados)
    espera_pronto(r["id"], tentativas=80, intervalo=5)     # vídeo leva alguns minutos na Meta
    pub = _chamada("POST", f"{conta}/media_publish", {"creation_id": r["id"]})
    try:
        link = _chamada("GET", pub["id"], {"fields": "permalink"}).get("permalink", "")
    except ErroMeta:
        link = ""
    return {"id": pub["id"], "permalink": link}


def publica(post: dict) -> dict:
    if post.get("video"):
        return publica_reel(post)
    conta = os.environ["IG_ACCOUNT_ID"]
    urls = [url_publica(p) for p in post["imagens"]]
    if SIMULAR:
        print(f"   [simulação] publicaria {len(urls)} imagem(ns):")
        for u in urls:
            print(f"      {u}")
        return {"id": "SIMULADO", "permalink": ""}

    for u in urls:
        confere_url(u)

    if len(urls) == 1:
        r = _chamada("POST", f"{conta}/media", {"image_url": urls[0], "caption": post["legenda"]})
    else:
        filhos = []
        for u in urls:
            f = _chamada("POST", f"{conta}/media", {"image_url": u, "is_carousel_item": "true"})
            espera_pronto(f["id"])
            filhos.append(f["id"])
        r = _chamada("POST", f"{conta}/media", {
            "media_type": "CAROUSEL", "children": ",".join(filhos), "caption": post["legenda"],
        })
    espera_pronto(r["id"])
    pub = _chamada("POST", f"{conta}/media_publish", {"creation_id": r["id"]})
    try:
        link = _chamada("GET", pub["id"], {"fields": "permalink"}).get("permalink", "")
    except ErroMeta:
        link = ""
    return {"id": pub["id"], "permalink": link}


# ---------------------------------------------------------------- laço

def agora():
    return datetime.now(timezone.utc)


def duracao(td):
    minutos = int(td.total_seconds() // 60)
    h, m = divmod(minutos, 60)
    return f"{h} h {m} min" if h else f"{m} min"


def main():
    falhas = []

    # 1. Algo ficou preso em "publicando"? A execução anterior caiu no meio.
    for preso in sorted(PUBLICANDO.glob("*.json")):
        post = json.loads(preso.read_text(encoding="utf-8-sig"))
        post["detalhe"] = ("A execução caiu durante o envio. CONFIRA no Instagram se o post "
                           "saiu antes de agendar de novo.")
        move(preso, ERROS, post)
        falhas.append(f"{preso.name}: preso em 'publicando' — conferir no Instagram")
    if falhas:
        salva_estado("Posts presos em 'publicando' movidos para erros")

    # 2. Posts da fila cujo horário chegou, do mais antigo para o mais novo.
    pendentes = []
    for arq in FILA.glob("*.json"):
        post = json.loads(arq.read_text(encoding="utf-8-sig"))
        quando = datetime.fromisoformat(post["publicar_em"])
        if quando <= agora():
            pendentes.append((quando, arq, post))
    pendentes.sort(key=lambda x: x[0])

    if not pendentes:
        print("Nenhum post no horário. Nada a fazer.")

    for quando, arq, post in pendentes:
        nome = arq.name
        print(f"-> {nome} (marcado para {quando.astimezone(BRT):%d/%m/%Y %H:%M} BRT)")

        atraso = agora() - quando
        if atraso > TOLERANCIA_ATRASO:
            post["detalhe"] = (f"Segurado: o horário passou há {duracao(atraso)} (mais de 3 h). "
                               "Não publiquei fora de hora — reagende.")
            move(arq, ERROS, post)
            salva_estado(f"Segurado (atrasado): {nome}")
            falhas.append(f"{nome}: atrasado, segurado")
            continue

        erros = regras.problemas_post(post)
        if erros:
            post["detalhe"] = "Barrado na validação: " + "; ".join(erros)
            move(arq, ERROS, post)
            salva_estado(f"Barrado na validação: {nome}")
            falhas.append(f"{nome}: {post['detalhe']}")
            continue

        # Antiduplicata: marca "publicando" e grava ANTES de falar com a Meta.
        post["status"] = "publicando"
        em_envio = move(arq, PUBLICANDO, post)
        salva_estado(f"Publicando: {nome}")

        try:
            resultado = publica(post)
        except ErroMeta as e:
            post["status"] = "erro"
            post["detalhe"] = str(e)
            move(em_envio, ERROS, post)
            salva_estado(f"Erro ao publicar: {nome}")
            falhas.append(f"{nome}: {e}")
            continue

        post["status"] = "publicado"
        post["publicado_em"] = agora().astimezone(BRT).isoformat(timespec="minutes")
        post["media_id"] = resultado["id"]
        post["link"] = resultado["permalink"]
        if atraso > timedelta(minutes=20):
            post["detalhe"] = f"publicado com atraso de {duracao(atraso)}"
        move(em_envio, PUBLICADOS, post)
        salva_estado(f"Publicado: {nome}")
        print(f"   publicado: {resultado['permalink'] or resultado['id']}")

    if falhas:
        print("\nFALHAS:")
        for f in falhas:
            print(f"  - {f}")
        sys.exit(1)   # execução vermelha → o GitHub manda e-mail


if __name__ == "__main__":
    main()
