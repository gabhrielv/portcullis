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
from portcullis.modelos import (
    Achado,
    Contexto,
    Evento,
    Evidencia,
    FaixaLinhas,
    Resposta,
    Severidade,
)
from portcullis.persistencia.dynamo import gravar_auditoria

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NOME_ACHADOS = "achados.json"
NOME_CONTEXTO = "contexto.json"
NOME_EVIDENCIAS = "evidencias.json"


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
        cwes=tuple(dados.get("cwes") or ()),
    )


def _resposta_de(bruto) -> Resposta:
    """Valor fora do vocabulário vira `nao_sei`, que bloqueia.

    Levantar aqui derrubaria a publicadora e o Check Run ficaria `in_progress`
    para sempre — o portão mudo é pior desfecho que o portão fechado.
    """
    try:
        return Resposta(str(bruto).strip().lower())
    except ValueError:
        return Resposta.NAO_SEI


def _evidencia_de(dados: dict) -> Evidencia:
    return Evidencia(
        chave=dados["chave"],
        entrada_controlavel=_resposta_de(dados.get("entrada_controlavel")),
        sanitizacao_encontrada=_resposta_de(dados.get("sanitizacao_encontrada")),
        prova=dados.get("prova"),
        prova_valida=bool(dados.get("prova_valida")),
        raciocinio=dados.get("raciocinio", ""),
        passos=int(dados.get("passos", 0)),
        tokens=int(dados.get("tokens", 0)),
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

    # A chave que chega é a do evidencias.json; os achados vêm do lado.
    resultado = _ler_json(bucket, f"{prefixo_saida}/{NOME_ACHADOS}")
    contexto = _contexto_de(_ler_json(bucket, f"{prefixo_entrada}/{NOME_CONTEXTO}"))
    evidencias_brutas = _ler_json(bucket, chave)

    if resultado.get("ok"):
        evidencias = {
            dados["chave"]: _evidencia_de(dados)
            for dados in evidencias_brutas.get("evidencias", [])
        }
        faltaram = evidencias_brutas.get("nao_investigados", 0)
        motivo = evidencias_brutas.get("motivo")
        if faltaram:
            aviso = f"{faltaram} achado(s) ficaram sem investigação"
            motivo = f"{motivo}; {aviso}" if motivo else aviso
        veredito = decidir(
            [_achado_de(a) for a in resultado["achados"]],
            contexto,
            evidencias=evidencias,
            degradado=bool(evidencias_brutas.get("degradado")),
            motivo=motivo,
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
        evidencias=evidencias_brutas.get("evidencias", []),
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
