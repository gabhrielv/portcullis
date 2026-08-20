"""Lambda investigadora: achados.json -> loop -> evidencias.json.

Ela LÊ CÓDIGO DE TERCEIRO e **não tem token do GitHub** — é a D14 continuando
de pé depois da D20. Fica fora da VPC porque precisa alcançar a API do modelo,
e o analisador não tem rota para lugar nenhum.

Ela nunca morre calada: se morrer sem escrever, a publicadora não acorda, o
Check Run fica `in_progress` para sempre e ninguém recebe motivo nenhum.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
import urllib.parse
from functools import cache
from pathlib import Path

import boto3

from pra.agente.ferramentas import Caixa
from pra.agente.loop import MOTIVO_PROVEDOR, investigar
from pra.agente.prompt import VERSAO_PROMPT
from pra.analisador.pacote import NOME_CODIGO, NOME_CONTEXTO, extrair, ler_contexto
from pra.config import obrigatoria, parametro_ssm
from pra.decisao.regra import decidir, investigavel, silencia_por_evidencia
from pra.llm.cliente import CotaEsgotada, ProvedorIndisponivel
from pra.llm.groq import ClienteGroq
from pra.modelos import Achado, Evidencia, Severidade

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

NOME_EVIDENCIAS = "evidencias.json"

# Ver M2-4. 10 × 8 passos somados aos ~4 min do semgrep encostam no teto de
# 15 min que o workflow do alvo espera.
TETO_ACHADOS = 10
# Abaixo disto a função para e escreve o que tem. Sem watchdog, o estouro de
# tempo mata a Lambda antes de qualquer escrita.
PISO_TEMPO_MS = 60_000

ESPACO_METRICAS = "pra"


@cache
def _cliente_s3():
    return boto3.client("s3")


def _cliente_llm():
    return ClienteGroq(
        parametro_ssm(obrigatoria("PRA_PARAM_CHAVE_LLM")),
        parametro_ssm(obrigatoria("PRA_PARAM_MODELO_LLM")),
    )


def _ler_json(bucket: str, chave: str) -> dict:
    return json.loads(_cliente_s3().get_object(Bucket=bucket, Key=chave)["Body"].read())


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


def _serializar(evidencia: Evidencia) -> dict:
    return {
        "chave": evidencia.chave,
        "entrada_controlavel": evidencia.entrada_controlavel.value,
        "sanitizacao_encontrada": evidencia.sanitizacao_encontrada.value,
        "prova": evidencia.prova,
        "prova_valida": evidencia.prova_valida,
        "raciocinio": evidencia.raciocinio,
        "passos": evidencia.passos,
        "tokens": evidencia.tokens,
    }


def _metrica(nome: str, valor: int) -> None:
    """Formato embutido: o CloudWatch extrai do log, sem PutMetricData e sem
    custo. A D17 exige que degradar seja visível."""
    print(
        json.dumps(
            {
                "_aws": {
                    "Timestamp": int(time.time() * 1000),
                    "CloudWatchMetrics": [
                        {
                            "Namespace": ESPACO_METRICAS,
                            "Dimensions": [[]],
                            "Metrics": [{"Name": nome, "Unit": "Count"}],
                        }
                    ],
                },
                nome: valor,
            }
        )
    )


ORDEM_SEVERIDADE = {Severidade.ERRO: 0, Severidade.AVISO: 1, Severidade.INFO: 2}


def _a_investigar(resultado: dict, contexto) -> list[Achado]:
    """Pré-tria com a regra: só achado que BLOQUEARIA vale token.

    A regra é pura e barata, e roda de novo na publicadora com a evidência na
    mão. Ela continua sendo a única autoridade — aqui ela só diz onde olhar.

    A ordenação não é cosmética: quando há mais bloqueantes que o teto, ela é
    que decide QUAIS entram. Sem ordem estável, reanalisar o mesmo commit
    investigaria um conjunto diferente e poderia dar outro veredito. É a ordem
    da D16 — severidade, depois arquivo:linha — com a regra desempatando, já
    que duas regras na mesma linha ficariam à mercê da ordem do semgrep.
    """
    achados = [_achado_de(a) for a in resultado.get("achados", [])]
    # `investigavel` também: a regra já recusaria a evidência desses achados, e
    # perguntar mesmo assim é gastar cota numa pergunta que não tem resposta.
    bloqueantes = [a for a in decidir(achados, contexto).bloqueantes if investigavel(a)]
    return sorted(
        bloqueantes,
        key=lambda a: (ORDEM_SEVERIDADE[a.severidade], a.caminho, a.linha_inicio, a.regra),
    )


def _investigar_todos(
    bloqueantes, caixa, cliente, contexto_lambda
) -> tuple[list[Evidencia], int]:
    evidencias: list[Evidencia] = []
    nao_investigados = 0

    for posicao, achado in enumerate(bloqueantes):
        if posicao >= TETO_ACHADOS:
            nao_investigados = len(bloqueantes) - posicao
            logger.info("teto de %d achados atingido", TETO_ACHADOS)
            break
        if contexto_lambda.get_remaining_time_in_millis() < PISO_TEMPO_MS:
            nao_investigados = len(bloqueantes) - posicao
            logger.info("watchdog: parando com %d por investigar", nao_investigados)
            break
        evidencias.append(investigar(achado, caixa, cliente))

    return evidencias, nao_investigados


def _processar(bucket: str, chave: str, contexto_lambda) -> None:
    prefixo_saida = chave.rsplit("/", 1)[0]
    prefixo_entrada = prefixo_saida.replace("saida/", "entrada/", 1)

    saida: dict = {
        "ok": False,
        "degradado": True,
        "motivo": None,
        "modelo": None,
        "versao_prompt": VERSAO_PROMPT,
        "nao_investigados": 0,
        "recusados_pelo_provedor": 0,
        "evidencias": [],
    }
    # Contado aqui, não a partir de `saida`: silenciar é decisão da regra, e
    # `len(evidencias)` contaria achado investigado, não achado silenciado.
    silenciaveis = 0

    try:
        resultado = _ler_json(bucket, chave)
        if not resultado.get("ok"):
            # O semgrep falhou. Não há o que investigar, mas a publicadora
            # precisa acordar para virar action_required.
            saida |= {"ok": True, "degradado": False, "motivo": "analise falhou"}
        else:
            with tempfile.TemporaryDirectory(dir="/tmp") as temporario:
                pasta = Path(temporario)
                for nome in (NOME_CODIGO, NOME_CONTEXTO):
                    _cliente_s3().download_file(
                        Bucket=bucket,
                        Key=f"{prefixo_entrada}/{nome}",
                        Filename=str(pasta / nome),
                    )
                contexto = ler_contexto(pasta / NOME_CONTEXTO)
                raiz = extrair(pasta / NOME_CODIGO, pasta / "arvore")

                bloqueantes = _a_investigar(resultado, contexto)
                cliente = _cliente_llm()
                # Registrado antes de investigar, e de propósito fora do `|=`
                # de sucesso: execução que degradou no meio precisa dizer qual
                # modelo tinha sido escolhido.
                saida["modelo"] = cliente.modelo
                evidencias, faltaram = _investigar_todos(
                    bloqueantes, Caixa(raiz), cliente, contexto_lambda
                )
                silenciaveis = sum(1 for e in evidencias if silencia_por_evidencia(e))
                recusados = sum(
                    1 for e in evidencias if e.raciocinio.startswith(MOTIVO_PROVEDOR)
                )
                # Recusa isolada e' ruido normal do provedor e nao degrada nada:
                # aquele achado vira `nao_sei` e bloqueia. Mas se TODO achado
                # investigado foi recusado, ninguem investigou coisa alguma —
                # tudo bloqueia, o que e' seguro, e reportar `degradado: false`
                # esconderia uma queda do provedor. D17: degradar em silencio e'
                # pior que falhar.
                saida |= {
                    "ok": True,
                    "degradado": bool(evidencias) and recusados == len(evidencias),
                    "evidencias": [_serializar(e) for e in evidencias],
                    "nao_investigados": faltaram,
                    "recusados_pelo_provedor": recusados,
                }
    except (CotaEsgotada, ProvedorIndisponivel) as falha:
        # D17: degrada para o modo marco 1. Sem evidência, a regra bloqueia
        # mais — nunca menos.
        saida |= {"ok": True, "motivo": f"{type(falha).__name__}: {falha}"}
    except Exception as falha:
        saida |= {"motivo": f"{type(falha).__name__}: {falha}"}
        logger.exception("investigacao falhou")

    if saida["degradado"]:
        _metrica("ExecucoesDegradadas", 1)
    _metrica("AchadosSilenciadosPorEvidencia", silenciaveis)

    _gravar(bucket, f"{prefixo_saida}/{NOME_EVIDENCIAS}", saida)
    logger.info(
        "evidencia gravada: %s evidencias=%d nao_investigados=%d recusados=%d degradado=%s",
        prefixo_saida,
        len(saida["evidencias"]),
        saida["nao_investigados"],
        saida["recusados_pelo_provedor"],
        saida["degradado"],
    )


def _gravar(bucket: str, chave: str, dados: dict) -> None:
    with tempfile.NamedTemporaryFile("w", dir="/tmp", suffix=".json") as arquivo:
        json.dump(dados, arquivo, indent=2)
        arquivo.flush()
        _cliente_s3().upload_file(arquivo.name, bucket, chave)


def lambda_handler(evento_lambda: dict, contexto_lambda) -> dict:
    registros = evento_lambda.get("Records", [])
    for registro in registros:
        bucket = registro["s3"]["bucket"]["name"]
        chave = urllib.parse.unquote_plus(registro["s3"]["object"]["key"])
        _processar(bucket, chave, contexto_lambda)
    return {"processados": len(registros)}
