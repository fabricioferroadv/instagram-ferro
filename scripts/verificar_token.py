"""Confere a saúde do token da Meta uma vez por semana.

Falha (e o GitHub manda e-mail) quando:
  - o token não é mais válido;
  - falta a permissão de publicar;
  - o prazo de acesso a dados (data_access_expires_at) vence em menos de 21 dias.
    Esse é o prazo que o sistema do Dr. Toni esquecia de vigiar. Para renovar,
    basta reautorizar o app na Meta (ver README).

Também grava status/token.json — o commit semanal mantém o repositório "ativo",
o que impede o GitHub de desligar o agendamento após 60 dias sem movimento.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v26.0')}"
RAIZ = Path(__file__).resolve().parent.parent
AVISAR_COM_DIAS = 21
BRT = timezone(timedelta(hours=-3))


def get(caminho, params):
    url = f"{GRAPH}/{caminho}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def data(ts):
    if not ts:
        return "nunca"
    return datetime.fromtimestamp(ts, BRT).strftime("%d/%m/%Y")


def main():
    token = os.environ["IG_ACCESS_TOKEN"]
    app_id, app_secret = os.environ.get("FB_APP_ID"), os.environ.get("FB_APP_SECRET")
    quem_pergunta = f"{app_id}|{app_secret}" if app_id and app_secret else token

    info = get("debug_token", {"input_token": token, "access_token": quem_pergunta})["data"]
    problemas = []

    if not info.get("is_valid"):
        problemas.append("token INVÁLIDO — gerar um novo (ver README)")
    if "instagram_content_publish" not in info.get("scopes", []):
        problemas.append("falta a permissão instagram_content_publish")

    acesso = info.get("data_access_expires_at") or 0
    if acesso:
        faltam = datetime.fromtimestamp(acesso, timezone.utc) - datetime.now(timezone.utc)
        if faltam < timedelta(days=AVISAR_COM_DIAS):
            problemas.append(f"acesso a dados vence em {faltam.days} dias ({data(acesso)}) — "
                             "reautorize o app na Meta")

    excesso = {"instagram_manage_messages", "instagram_manage_comments"} & set(info.get("scopes", []))
    if excesso:
        print(f"Aviso: o token tem permissões que não usamos (LGPD): {', '.join(sorted(excesso))}")

    cota = {}
    try:
        cota = get(f"{os.environ['IG_ACCOUNT_ID']}/content_publishing_limit",
                   {"fields": "quota_usage,config", "access_token": token}).get("data", [{}])[0]
    except Exception as e:  # cota é informativa; não derruba a verificação
        print(f"Não consegui ler a cota: {e}")

    estado = {
        "verificado_em": datetime.now(BRT).isoformat(timespec="minutes"),
        "valido": info.get("is_valid"),
        "tipo": info.get("type"),
        "token_expira": data(info.get("expires_at")),
        "acesso_a_dados_expira": data(acesso),
        "permissoes": sorted(info.get("scopes", [])),
        "posts_ultimas_24h": cota.get("quota_usage"),
        "problemas": problemas,
    }
    (RAIZ / "status").mkdir(exist_ok=True)
    (RAIZ / "status" / "token.json").write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(estado, ensure_ascii=False, indent=2))

    if problemas:
        sys.exit(1)


if __name__ == "__main__":
    main()
