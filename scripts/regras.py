"""Regras de validação de um post antes de publicar.

Usado nos dois lados: no seu computador (ao agendar) e no GitHub (antes de
enviar à Meta). Só biblioteca padrão do Python — nada para instalar.
"""
import re
import unicodedata

LIMITE_LEGENDA = 2200      # caracteres (limite do Instagram)
LIMITE_HASHTAGS = 5        # regra do escritório (03/11/2026); o Instagram aceita até 30
HASHTAG_OBRIGATORIA = "#advogadotrabalhista"
LIMITE_MENCOES = 20
MIN_IMAGENS = 1
MAX_IMAGENS = 10           # carrossel pela API: até 10 itens
MAX_BYTES_IMAGEM = 8 * 1024 * 1024

# Provimento 205/2021 da OAB — expressões que configuram captação de
# clientela, mercantilização ou promessa de resultado. A comparação ignora
# maiúsculas e acentos. Um termo só passa se for liberado no próprio post
# (campo "termos_liberados"), de forma consciente.
TERMOS_PROIBIDOS_OAB = [
    # captação direta / chamada para contratar
    "me chama no direct", "me chamar no direct", "chama no direct",
    "chamar no direct", "chama no privado", "me chama no privado",
    "manda dm", "mande dm", "dm para consulta", "direct para consulta",
    "agende uma consulta", "agende sua consulta", "agendar uma consulta",
    "marque uma consulta", "marque sua consulta", "consulta gratuita",
    "consulta gratis", "avaliacao gratuita", "atendimento gratuito",
    "chama no whatsapp", "chame no whatsapp", "me chama no whats",
    "link na bio para contratar", "contrate", "contrate ja",
    # promessa de resultado
    "resultado garantido", "garantimos", "garantia de resultado",
    "100% de sucesso", "causa ganha", "ganho garantido", "sem risco",
    # autopromoção comparativa
    "melhor advogado", "melhor escritorio", "o mais experiente",
    # preço / mercantilização
    "honorarios a partir", "preco", "desconto", "promocao", "orcamento gratis",
    "parcelamos", "so paga se ganhar", "so paga no final",
]


def _normaliza(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower())


def termos_oab_encontrados(legenda: str, liberados=()) -> list[str]:
    texto = _normaliza(legenda)
    liberados_n = {_normaliza(t) for t in liberados}
    achados = []
    for termo in TERMOS_PROIBIDOS_OAB:
        t = _normaliza(termo)
        if t in liberados_n:
            continue
        # palavra inteira, para "preco" não pegar "apreco" etc.
        if re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", texto):
            achados.append(termo)
    return achados


def problemas_legenda(legenda: str, liberados=()) -> list[str]:
    erros = []
    if not legenda or not legenda.strip():
        erros.append("legenda vazia")
        return erros
    if len(legenda) > LIMITE_LEGENDA:
        erros.append(f"legenda com {len(legenda)} caracteres (máximo {LIMITE_LEGENDA})")
    hashtags = [h.lower() for h in re.findall(r"(?<!\w)#\w+", legenda)]
    if len(hashtags) > LIMITE_HASHTAGS:
        erros.append(f"{len(hashtags)} hashtags (máximo {LIMITE_HASHTAGS})")
    if HASHTAG_OBRIGATORIA not in hashtags:
        erros.append(f"falta a hashtag obrigatória {HASHTAG_OBRIGATORIA}")
    n_menc = len(re.findall(r"(?<!\w)@[\w.]+", legenda))
    if n_menc > LIMITE_MENCOES:
        erros.append(f"{n_menc} menções @ (máximo {LIMITE_MENCOES})")
    oab = termos_oab_encontrados(legenda, liberados)
    if oab:
        erros.append(
            "possível violação do Provimento 205/2021 da OAB — expressões: "
            + ", ".join(f'"{t}"' for t in oab)
        )
    return erros


def problemas_post(post: dict) -> list[str]:
    """Confere a estrutura do arquivo da fila (sem olhar os pixels)."""
    erros = []
    imagens = post.get("imagens") or []
    if post.get("video"):                       # Reel: um vídeo .mp4 (+ capa opcional em JPEG)
        if not post["video"].lower().endswith(".mp4"):
            erros.append("o vídeo do Reel precisa ser .mp4")
        imagens = [post["capa"]] if post.get("capa") else []
    elif not (MIN_IMAGENS <= len(imagens) <= MAX_IMAGENS):
        erros.append(f"{len(imagens)} imagens (precisa de {MIN_IMAGENS} a {MAX_IMAGENS})")
    for img in imagens:
        if not img.lower().endswith((".jpg", ".jpeg")):
            erros.append(f"{img}: só JPEG é aceito pela Meta")
    if not post.get("publicar_em"):
        erros.append("falta a data/hora de publicação")
    erros += problemas_legenda(post.get("legenda", ""), post.get("termos_liberados", []))
    return erros
