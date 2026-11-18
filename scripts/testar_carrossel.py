"""Teste seguro de carrossel: cria os contêineres de um carrossel na Meta e espera processar.

NÃO publica (nunca chama media_publish). Serve para confirmar que a Meta aceita imagens
num formato novo (ex.: 3:4 = 1080x1440). Uso (no GitHub Actions):
    python3 scripts/testar_carrossel.py midia/_teste/34-01.jpg midia/_teste/34-02.jpg
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import publicar as P  # noqa: E402


def main():
    conta = os.environ["IG_ACCOUNT_ID"]
    filhos = []
    try:
        for caminho in sys.argv[1:]:
            url = P.url_publica(caminho)
            print("Imagem:", url)
            f = P._chamada("POST", f"{conta}/media", {"image_url": url, "is_carousel_item": "true"})
            P.espera_pronto(f["id"])
            print("  item aceito:", f["id"])
            filhos.append(f["id"])
        c = P._chamada("POST", f"{conta}/media", {"media_type": "CAROUSEL", "children": ",".join(filhos),
                                                   "caption": "teste - não publicar"})
        P.espera_pronto(c["id"])
        info = P._chamada("GET", c["id"], {"fields": "status_code,status"})
        print("Contêiner do carrossel:", c["id"], info)
        print("RESULTADO: a Meta ACEITOU o carrossel neste formato. Nada foi publicado.")
    except P.ErroMeta as e:
        print("RESULTADO: a Meta RECUSOU ->", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
