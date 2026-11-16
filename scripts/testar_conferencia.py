"""Teste seguro da antiduplicata: só LÊ o perfil, nunca publica.

Para os últimos posts de publicados/, confere se ja_no_instagram() os encontra
pela legenda. Todos devem dar "ACHOU". Uso (GitHub Actions → Run workflow).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import publicar as P  # noqa: E402


def main():
    arquivos = sorted(P.PUBLICADOS.glob("*.json"))[-5:]
    falhou = False
    for arq in arquivos:
        post = json.loads(arq.read_text(encoding="utf-8-sig"))
        achado = P.ja_no_instagram(post)
        if achado and achado["id"] == post.get("media_id"):
            print(f"ACHOU     {arq.stem} -> {achado['permalink']}")
        elif achado:
            print(f"ACHOU*    {arq.stem} -> {achado['permalink']} (id diferente do registrado: {post.get('media_id')})")
        else:
            print(f"NÃO ACHOU {arq.stem}")
            falhou = True
    sys.exit(1 if falhou else 0)


if __name__ == "__main__":
    main()
