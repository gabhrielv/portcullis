"""Lambda buscadora: fila -> pacote no S3 -> analisador.

Esta função TEM o token do GitHub e NÃO lê o código que baixa. O analisador lê
o código e NÃO tem token nenhum. Essa é a separação de privilégio da D14 — se
alguém juntar as duas responsabilidades aqui, a defesa some.
"""

from __future__ import annotations

import json
import logging
import tempfile
from functools import cache
from pathlib import Path

import boto3

from portcullis.analisador.pacote import NOME_CODIGO, NOME_CONTEXTO, escrever_contexto
from portcullis.buscador.github_api import (
    linhas_tocadas_de_pr,
    linhas_tocadas_de_push,
    tarball_para_s3,
)
from portcullis.config import obrigatoria, parametro_ssm
from portcullis.github.auth import token_de_instalacao
from portcullis.github.checks import criar_em_progresso
from portcullis.modelos import Contexto, Evento

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@cache
def _cliente_s3():
    return boto3.client("s3")


@cache
def _cliente_dynamo():
    return boto3.client("dynamodb")


@cache
def _cliente_lambda():
    return boto3.client("lambda")


def _prefixo(trabalho: dict) -> str:
    return f"entrada/{trabalho['owner']}/{trabalho['repo']}/{trabalho['head_sha']}"


def _chave_lock(trabalho: dict) -> dict:
    # Single-table design: a chave de ordenação guarda dois tipos de item na
    # mesma tabela — `lock#...` aqui, o registro de auditoria na T9.
    return {
        "repo": {"S": f"{trabalho['owner']}#{trabalho['repo']}"},
        "sha": {"S": f"lock#{trabalho['head_sha']}"},
    }


def _reservar(trabalho: dict) -> bool:
    """Escrita condicional: atômica, então não há janela entre conferir e agir.

    A fila do SQS entrega ao menos uma vez — não é bug, é o contrato. Sem isto,
    a mesma mensagem entregue duas vezes paga duas análises do mesmo commit.
    """
    dynamo = _cliente_dynamo()
    try:
        dynamo.put_item(
            TableName=obrigatoria("PORTCULLIS_TABELA"),
            Item=_chave_lock(trabalho),
            ConditionExpression="attribute_not_exists(sha)",
        )
        return True
    except dynamo.exceptions.ConditionalCheckFailedException:
        return False


def _liberar(trabalho: dict) -> None:
    """Desfaz a reserva quando o trabalho falha.

    Sem isto a falha vira silêncio: o SQS reentrega, a reentrega cai no lock,
    pula, devolve sucesso — e nenhuma análise acontece sem nada avisar.
    """
    try:
        _cliente_dynamo().delete_item(
            TableName=obrigatoria("PORTCULLIS_TABELA"), Key=_chave_lock(trabalho)
        )
    except Exception:
        logger.exception("nao consegui liberar o lock de %s", trabalho["head_sha"])


def _montar_contexto(trabalho: dict, token: str) -> Contexto:
    if trabalho["evento"] == "pull_request":
        tocadas, tudo_novo = linhas_tocadas_de_pr(
            token, trabalho["owner"], trabalho["repo"], trabalho["numero_pr"]
        )
    else:
        tocadas, tudo_novo = linhas_tocadas_de_push(
            token,
            trabalho["owner"],
            trabalho["repo"],
            trabalho.get("base_sha"),
            trabalho["head_sha"],
        )

    return Contexto(
        owner=trabalho["owner"],
        repo=trabalho["repo"],
        head_sha=trabalho["head_sha"],
        evento=Evento(trabalho["evento"]),
        linhas_tocadas=tocadas,
        numero_pr=trabalho.get("numero_pr"),
        base_sha=trabalho.get("base_sha"),
        tudo_novo=tudo_novo,
    )


def _montar_pacote(trabalho: dict, bucket: str, prefixo: str) -> None:
    token = token_de_instalacao(
        obrigatoria("PORTCULLIS_GITHUB_APP_ID"),
        parametro_ssm(obrigatoria("PORTCULLIS_PARAM_CHAVE_APP")),
        trabalho["owner"],
        trabalho["repo"],
    )

    # Sinal imediato no PR: a análise leva ~4 min, e sem isto o
    # desenvolvedor passa esse tempo sem saber se algo está acontecendo.
    # Falhar aqui não pode custar a análise — a checagem é sinal para humano,
    # e a publicadora cria uma no fim se esta não existir.
    try:
        criar_em_progresso(token, trabalho["owner"], trabalho["repo"], trabalho["head_sha"])
    except Exception:
        logger.exception("nao consegui abrir a checagem em progresso")

    tarball_para_s3(
        token,
        trabalho["owner"],
        trabalho["repo"],
        trabalho["head_sha"],
        bucket,
        f"{prefixo}/{NOME_CODIGO}",
    )

    contexto = _montar_contexto(trabalho, token)
    with tempfile.TemporaryDirectory() as temporario:
        caminho = Path(temporario) / NOME_CONTEXTO
        escrever_contexto(contexto, caminho)
        _cliente_s3().put_object(
            Bucket=bucket, Key=f"{prefixo}/{NOME_CONTEXTO}", Body=caminho.read_bytes()
        )


def _processar(trabalho: dict) -> None:
    prefixo = _prefixo(trabalho)

    if not _reservar(trabalho):
        logger.info("duplicata ignorada: %s", prefixo)
        return

    bucket = obrigatoria("PORTCULLIS_BUCKET_PACOTES")
    try:
        _montar_pacote(trabalho, bucket, prefixo)
        # Assíncrono: esperar os ~2 minutos da análise pagaria duas Lambdas ao
        # mesmo tempo, e a resposta não seria usada por ninguém.
        # Dentro do try junto com o pacote: o pacote existir no S3 não adianta
        # se a análise nunca foi disparada, e aí a reentrega precisa poder
        # tentar de novo em vez de bater no lock e devolver sucesso.
        _cliente_lambda().invoke(
            FunctionName=obrigatoria("PORTCULLIS_FUNCAO_ANALISADOR"),
            InvocationType="Event",
            Payload=json.dumps({"bucket": bucket, "prefixo": prefixo}),
        )
    except Exception:
        _liberar(trabalho)
        raise

    logger.info(
        "pacote montado e analise disparada: %s/%s evento=%s sha=%s",
        trabalho["owner"],
        trabalho["repo"],
        trabalho["evento"],
        trabalho["head_sha"],
    )


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    registros = evento_lambda.get("Records", [])
    for registro in registros:
        _processar(json.loads(registro["body"]))
    return {"processados": len(registros)}
