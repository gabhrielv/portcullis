"""GET /veredito/{owner}/{repo}/{sha} — o que o passo de deploy consulta.

Fail-closed por construção: SHA sem registro devolve 404 e `liberado: false`.
É isso que cobre push direto e bypass de administrador — commit que nunca foi
analisado não tem veredito, e não ter veredito reprova.

Responde SE passou, nunca O QUE foi encontrado: o endpoint é público, e listar
vulnerabilidade nele entregaria a quem só sabe um SHA o mapa do que atacar.
"""

from __future__ import annotations

import json
import logging
from functools import cache

import boto3

from portcullis.config import obrigatoria

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

VEREDITO_QUE_LIBERA = "liberado"


@cache
def _tabela(nome: str):
    return boto3.resource("dynamodb").Table(nome)


def _resposta(codigo: int, corpo: dict) -> dict:
    return {
        "statusCode": codigo,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(corpo),
    }


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    parametros = evento_lambda.get("pathParameters") or {}
    owner = parametros.get("owner")
    repo = parametros.get("repo")
    sha = parametros.get("sha")

    if not all((owner, repo, sha)):
        return _resposta(400, {"erro": "parametros faltando", "liberado": False})

    resultado = _tabela(obrigatoria("PORTCULLIS_TABELA")).get_item(
        Key={"repo": f"{owner}#{repo}", "sha": sha}
    )
    item = resultado.get("Item")

    if item is None:
        logger.info("veredito desconhecido: %s/%s sha=%s", owner, repo, sha)
        return _resposta(404, {"veredito": "desconhecido", "liberado": False})

    veredito = item["veredito"]
    liberado = veredito == VEREDITO_QUE_LIBERA
    logger.info("veredito consultado: %s/%s sha=%s estado=%s", owner, repo, sha, veredito)

    return _resposta(
        200 if liberado else 403,
        {
            "veredito": veredito,
            "liberado": liberado,
            "versao_regra": item["versao_regra"],
            "horario": item["horario"],
        },
    )
