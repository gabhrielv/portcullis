from dataclasses import FrozenInstanceError

import pytest

from portcullis.modelos import (
    Achado,
    Contexto,
    Evento,
    FaixaLinhas,
    Severidade,
)


def test_faixa_detecta_sobreposicao_parcial():
    faixa = FaixaLinhas(inicio=10, fim=20)
    assert faixa.intersecta(18, 25) is True
    assert faixa.intersecta(1, 10) is True
    assert faixa.intersecta(21, 30) is False
    assert faixa.intersecta(1, 9) is False


def test_severidade_vem_do_vocabulario_do_semgrep():
    assert Severidade("ERROR") is Severidade.ERRO
    assert Severidade("WARNING") is Severidade.AVISO
    assert Severidade("INFO") is Severidade.INFO


def test_achado_e_imutavel():
    achado = Achado(
        regra="python.lang.security.audit.sqli",
        severidade=Severidade.ERRO,
        caminho="backend/app/repo/user.py",
        linha_inicio=88,
        linha_fim=88,
        mensagem="possível SQL injection",
    )
    with pytest.raises(FrozenInstanceError):
        achado.linha_inicio = 99


def test_contexto_de_push_nao_tem_numero_de_pr():
    ctx = Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PUSH,
        linhas_tocadas={},
    )
    assert ctx.numero_pr is None
    assert ctx.tudo_novo is False
