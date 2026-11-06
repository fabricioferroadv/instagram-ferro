"""Teste seguro de vídeo: cria um contêiner de Reel na Meta e espera processar.

NÃO publica (nunca chama media_publish). Serve para confirmar que a Meta consegue
baixar vídeos hospedados no GitHub. Uso (no GitHub Actions):
    python3 scripts/testar_video.py midia/_teste/teste.mp4
"""
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import publicar as P  # noqa: E402


def main():
    url = P.url_publica(sys.argv[1])
    print("URL:", url)
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
        print("Content-Type servido pelo GitHub:", r.headers.get("Content-Type"),
              "| tamanho:", r.headers.get("Content-Length"))
    conta = os.environ["IG_ACCOUNT_ID"]
    c = P._chamada("POST", f"{conta}/media", {"media_type": "REELS", "video_url": url,
                                               "caption": "teste - não publicar", "share_to_feed": "false"})
    print("Contêiner criado:", c["id"])
    try:
        P.espera_pronto(c["id"], tentativas=60, intervalo=5)
        print("RESULTADO: a Meta baixou e processou o vídeo (FINISHED). Hospedagem OK. Nada foi publicado.")
    except P.ErroMeta as e:
        print("RESULTADO: falhou ->", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
