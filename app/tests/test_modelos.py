from dataclasses import FrozenInstanceError

import pytest

from portcullis.modelos import (
    Achado,
    Contexto,
    Evento,
    Evidencia,
    FaixaLinhas,
    Resposta,
    Severidade,
    chave_do_achado,
)


def achado(**mudancas):
    campos = {
        "regra": "python.lang.security.audit.sqli",
        "severidade": Severidade.ERRO,
        "caminho": "backend/app/repo/user.py",
        "linha_inicio": 88,
        "linha_fim": 88,
        "mensagem": "possível SQL injection",
    }
    return Achado(**{**campos, **mudancas})


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


# ---------------------------------------------------------------------------
# A chave casa achado com evidência. Se ela deixar de distinguir dois achados,
# a evidência de um silencia o outro — e nada avisa.
# ---------------------------------------------------------------------------


def test_chave_e_estavel_para_o_mesmo_achado():
    assert chave_do_achado(achado()) == chave_do_achado(achado())


def test_chave_distingue_cada_componente():
    base = chave_do_achado(achado())
    assert chave_do_achado(achado(regra="outra.regra")) != base
    assert chave_do_achado(achado(caminho="outro/arquivo.py")) != base
    assert chave_do_achado(achado(linha_inicio=89)) != base
    assert chave_do_achado(achado(linha_fim=90)) != base


def test_chave_ignora_o_que_nao_identifica_o_achado():
    # Mensagem e categoria podem mudar quando o conjunto de regras é
    # atualizado. Se entrassem na chave, a evidência congelada deixaria de
    # casar depois de um `make regras`, sem ninguém entender por quê.
    base = chave_do_achado(achado())
    assert chave_do_achado(achado(mensagem="outra mensagem")) == base
    assert chave_do_achado(achado(categoria="security")) == base


def test_evidencia_e_imutavel():
    evidencia = Evidencia(
        chave="r|a.py|1|1",
        entrada_controlavel=Resposta.NAO,
        sanitizacao_encontrada=Resposta.NAO_SEI,
    )
    with pytest.raises(FrozenInstanceError):
        evidencia.entrada_controlavel = Resposta.SIM


def test_evidencia_nasce_sem_prova_valida():
    # O padrão precisa ser o que bloqueia: quem constrói uma Evidencia sem
    # passar por prova_valida não pode ganhar silêncio de graça.
    evidencia = Evidencia(
        chave="r|a.py|1|1",
        entrada_controlavel=Resposta.NAO_SEI,
        sanitizacao_encontrada=Resposta.SIM,
    )
    assert evidencia.prova_valida is False
    assert evidencia.prova is None
