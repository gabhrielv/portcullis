"""Lambda do webhook: valida a assinatura, enfileira, responde 200.

O GitHub desiste da entrega em ~10 s. Por isso esta função não baixa código,
não roda scanner e não invoca o analisador — ela só põe o trabalho na fila.
"""

from __future__ import annotations

import base64
import json
from functools import cache

import boto3

from portcullis.config import obrigatoria, parametro_ssm
from portcullis.webhook.assinatura import conferir_assinatura

EVENTOS_ACEITOS = frozenset({"pull_request", "push"})
# As outras ações (closed, labeled, assigned…) não mexem em código.
ACOES_DE_PR = frozenset({"opened", "synchronize", "reopened"})


@cache
def _cliente_sqs():
    return boto3.client("sqs")


def _resposta(codigo: int, mensagem: str) -> dict:
    return {"statusCode": codigo, "body": json.dumps({"mensagem": mensagem})}


def _corpo_bruto(evento_lambda: dict) -> bytes:
    """O HMAC do GitHub é calculado sobre os bytes que ele enviou.

    O API Gateway às vezes entrega o corpo em base64; conferir a assinatura
    contra a string codificada faria toda requisição legítima devolver 401.
    """
    bruto = evento_lambda.get("body") or ""
    if evento_lambda.get("isBase64Encoded"):
        return base64.b64decode(bruto)
    return bruto.encode()


def _extrair_trabalho(nome_evento: str, corpo: dict) -> dict | None:
    repositorio = corpo["repository"]
    comum = {
        "owner": repositorio["owner"]["login"],
        "repo": repositorio["name"],
    }

    if nome_evento == "pull_request":
        if corpo.get("action") not in ACOES_DE_PR:
            return None
        return {
            **comum,
            "evento": "pull_request",
            "head_sha": corpo["pull_request"]["head"]["sha"],
            "base_sha": corpo["pull_request"]["base"]["sha"],
            "numero_pr": corpo["number"],
        }

    # Push só na branch padrão: a branch do PR já é analisada pelo evento de
    # pull_request, e analisar de novo seria pagar duas vezes pelo mesmo commit.
    # Mas a branch padrão é obrigatória — o SHA que vai para produção nasce no
    # merge e nunca é o head do PR.
    if corpo.get("ref") != f"refs/heads/{repositorio['default_branch']}":
        return None
    if corpo.get("deleted"):
        return None
    return {
        **comum,
        "evento": "push",
        "head_sha": corpo["after"],
        "base_sha": corpo["before"],
        "numero_pr": None,
    }


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    corpo_bruto = _corpo_bruto(evento_lambda)
    cabecalhos = {k.lower(): v for k, v in (evento_lambda.get("headers") or {}).items()}

    segredo = parametro_ssm(obrigatoria("PORTCULLIS_PARAM_SEGREDO_WEBHOOK"))
    if not conferir_assinatura(
        corpo_bruto, cabecalhos.get("x-hub-signature-256"), segredo
    ):
        return _resposta(401, "assinatura inválida")

    nome_evento = cabecalhos.get("x-github-event", "")
    if nome_evento == "ping":
        return _resposta(200, "pong")
    if nome_evento not in EVENTOS_ACEITOS:
        return _resposta(200, f"evento {nome_evento} ignorado")

    trabalho = _extrair_trabalho(nome_evento, json.loads(corpo_bruto))
    if trabalho is None:
        return _resposta(200, "nada a fazer")

    _cliente_sqs().send_message(
        QueueUrl=obrigatoria("PORTCULLIS_FILA_URL"),
        MessageBody=json.dumps(trabalho),
    )
    return _resposta(200, "enfileirado")
