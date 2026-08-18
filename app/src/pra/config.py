"""Variáveis de ambiente e segredos do SSM, com falha cedo.

Falhar na primeira invocação é melhor que falhar no meio de uma análise: o erro
aparece no PR de teste, não no dia em que um PR importante depende disso.
"""

from __future__ import annotations

import os
import time
from functools import cache

import boto3

# O cache existe para não pagar uma chamada ao SSM por invocação, mas ele
# PRECISA expirar: cache eterno faz o container quente continuar conferindo
# contra um segredo já rotacionado, e o sintoma é toda entrega legítima virando
# 401 sem sinal nenhum. Cinco minutos é o teto de quanto tempo uma rotação leva
# para valer em todo lugar, sem intervenção.
VALIDADE_CACHE_S = 300

_cache: dict[str, tuple[float, str]] = {}


@cache
def _cliente_ssm():
    return boto3.client("ssm")


def obrigatoria(nome: str) -> str:
    valor = os.environ.get(nome)
    if not valor:
        raise RuntimeError(f"variável de ambiente {nome} não definida")
    return valor


def esquecer_parametros() -> None:
    """Descarta o cache. Usado nos testes e após rotacionar um segredo."""
    _cache.clear()


def parametro_ssm(nome: str) -> str:
    agora = time.monotonic()
    lembrado = _cache.get(nome)
    if lembrado is not None and agora - lembrado[0] < VALIDADE_CACHE_S:
        return lembrado[1]

    resposta = _cliente_ssm().get_parameter(Name=nome, WithDecryption=True)
    valor = resposta["Parameter"]["Value"]
    _cache[nome] = (agora, valor)
    return valor
