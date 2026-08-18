#!/usr/bin/env python
"""Sorteia um segredo de webhook novo e grava nos dois lados de uma vez.

O segredo precisa ser idêntico no GitHub (que assina cada entrega) e no SSM
(que o handler lê para conferir). Quando um humano copia o valor entre duas
telas, divergir é questão de tempo — e o sintoma é silencioso: toda entrega
legítima vira 401 e nenhuma análise acontece.

Aqui o valor é sorteado, escrito e descartado sem nunca aparecer na tela, no
histórico do shell ou num arquivo. Ninguém precisa vê-lo.

    python scripts/rotacionar_segredo.py --app-id 4589712
"""

from __future__ import annotations

import argparse
import secrets
import sys

import boto3
import requests

from pra.github.auth import jwt_do_app

CONFIG_DO_HOOK = "https://api.github.com/app/hook/config"
PARAMETRO_CHAVE = "/pra/github/chave-privada"
PARAMETRO_SEGREDO = "/pra/github/segredo-webhook"
TEMPO_LIMITE_S = 10


def principal(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--app-id", required=True)
    analisador.add_argument("--parametro-chave", default=PARAMETRO_CHAVE)
    analisador.add_argument("--parametro-segredo", default=PARAMETRO_SEGREDO)
    args = analisador.parse_args(argv)

    novo = secrets.token_hex(32)
    ssm = boto3.client("ssm")

    # SSM primeiro: se o GitHub falhar depois, ele segue assinando com o
    # segredo antigo e basta rodar de novo. Na ordem inversa, uma falha aqui
    # deixaria o GitHub assinando com um segredo que ninguém tem.
    ssm.put_parameter(
        Name=args.parametro_segredo,
        Value=novo,
        Type="SecureString",
        Overwrite=True,
    )

    chave = ssm.get_parameter(Name=args.parametro_chave, WithDecryption=True)
    token = jwt_do_app(args.app_id, chave["Parameter"]["Value"])

    resposta = requests.patch(
        CONFIG_DO_HOOK,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"secret": novo, "content_type": "json"},
        timeout=TEMPO_LIMITE_S,
    )

    if not resposta.ok:
        print(
            f"SSM atualizado, GitHub falhou: {resposta.status_code} {resposta.text}\n"
            "Os dois lados estão divergentes — rode de novo.",
            file=sys.stderr,
        )
        return 1

    print("segredo rotacionado nos dois lados")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
