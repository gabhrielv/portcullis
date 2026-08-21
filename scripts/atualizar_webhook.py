#!/usr/bin/env python
"""Aponta o webhook do GitHub App para a URL que o terraform acabou de criar.

Cada `terraform apply` cria um API Gateway novo, com ID novo — e a URL antiga,
que está gravada no App, deixa de existir. Sem isto, todo ciclo de trabalho
começa com dois cliques manuais no navegador.

Autentica com JWT assinado pela chave privada do próprio App, que já vive no
SSM: nenhum token pessoal a mais, nenhum segredo novo.

    python scripts/atualizar_webhook.py --app-id 123456 --url https://.../webhook
"""

from __future__ import annotations

import argparse
import sys

import requests

from portcullis.config import parametro_ssm
from portcullis.github.auth import jwt_do_app

CONFIG_DO_HOOK = "https://api.github.com/app/hook/config"
PARAMETRO_CHAVE = "/portcullis/github/chave-privada"
TEMPO_LIMITE_S = 10


def principal(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--app-id", required=True)
    analisador.add_argument("--url", required=True)
    analisador.add_argument("--parametro", default=PARAMETRO_CHAVE)
    args = analisador.parse_args(argv)

    token = jwt_do_app(args.app_id, parametro_ssm(args.parametro))

    resposta = requests.patch(
        CONFIG_DO_HOOK,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"url": args.url, "content_type": "json"},
        timeout=TEMPO_LIMITE_S,
    )

    if not resposta.ok:
        print(f"falhou: {resposta.status_code} {resposta.text}", file=sys.stderr)
        return 1

    print(f"webhook agora aponta para {resposta.json()['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
