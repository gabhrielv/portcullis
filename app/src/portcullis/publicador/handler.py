"""Lambda publicadora: evento do S3 -> regra -> Check Run + auditoria.

A REGRA MORA AQUI, nunca no analisador. O analisador produz evidência; quem
julga é quem publica. No marco 2 o agente entra entre os dois, e esta função
continua sendo a que decide.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from functools import cache

import boto3

from portcullis.config import obrigatoria, parametro_ssm
from portcullis.decisao.regra import decidir, nao_conclui
from portcullis.github.auth import token_de_instalacao
from portcullis.github.checks import publicar
from portcullis.modelos import Achado, Contexto, Evento, FaixaLinhas, Severidade
from portcullis.persistencia.dynamo import gravar_auditoria

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NOME_ACHADOS = "achados.json"
NOME_CONTEXTO = "contexto.json"


@cache
def _cliente_s3():
    return boto3.client("s3")


def _ler_json(bucket: str, chave: str) -> dict:
    objeto = _cliente_s3().get_object(Bucket=bucket, Key=chave)
    return json.loads(objeto["Body"].read())


def _achado_de(dados: dict) -> Achado:
    return Achado(
        regra=dados["regra"],
        severidade=Severidade(dados["severidade"]),
        caminho=dados["caminho"],
        linha_inicio=dados["linha_inicio"],
        linha_fim=dados["linha_fim"],
        mensagem=dados["mensagem"],
        categoria=dados.get("categoria"),
    )


def _contexto_de(dados: dict) -> Contexto:
    return Contexto(
        owner=dados["owner"],
        repo=dados["repo"],
        head_sha=dados["head_sha"],
        evento=Evento(dados["evento"]),
        linhas_tocadas={
            arquivo: tuple(FaixaLinhas(i, f) for i, f in faixas)
            for arquivo, faixas in dados["linhas_tocadas"].items()
        },
        numero_pr=dados.get("numero_pr"),
        base_sha=dados.get("base_sha"),
        tudo_novo=dados.get("tudo_novo", False),
    )


def _processar(bucket: str, chave: str) -> None:
    prefixo_saida = chave.rsplit("/", 1)[0]
    prefixo_entrada = prefixo_saida.replace("saida/", "entrada/", 1)

    resultado = _ler_json(bucket, chave)
    contexto = _contexto_de(_ler_json(bucket, f"{prefixo_entrada}/{NOME_CONTEXTO}"))

    if resultado.get("ok"):
        veredito = decidir(
            [_achado_de(a) for a in resultado["achados"]], contexto
        )
    else:
        # Falha do scanner NÃO vira success: não saber se há problema tem que
        # bloquear, com mensagem que diz o que houve.
        veredito = nao_conclui(resultado.get("erro") or "analise falhou")

    token = token_de_instalacao(
        obrigatoria("PORTCULLIS_GITHUB_APP_ID"),
        parametro_ssm(obrigatoria("PORTCULLIS_PARAM_CHAVE_APP")),
        contexto.owner,
        contexto.repo,
    )
    publicar(token, contexto.owner, contexto.repo, contexto.head_sha, veredito)

    gravar_auditoria(
        tabela=obrigatoria("PORTCULLIS_TABELA"),
        repo=f"{contexto.owner}#{contexto.repo}",
        sha=contexto.head_sha,
        veredito=veredito,
        hash_regras=resultado.get("hash_regras", ""),
    )

    logger.info(
        "veredito publicado: %s/%s sha=%s estado=%s bloqueantes=%d",
        contexto.owner,
        contexto.repo,
        contexto.head_sha,
        veredito.estado.value,
        len(veredito.bloqueantes),
    )


def lambda_handler(evento_lambda: dict, _contexto) -> dict:
    registros = evento_lambda.get("Records", [])
    for registro in registros:
        bucket = registro["s3"]["bucket"]["name"]
        # O S3 entrega a chave com codificacao de URL.
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        _processar(bucket, chave)
    return {"processados": len(registros)}
