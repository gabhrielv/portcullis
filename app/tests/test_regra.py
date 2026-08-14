from portcullis.decisao.regra import VERSAO_REGRA, decidir, nao_conclui
from portcullis.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Evento,
    FaixaLinhas,
    Severidade,
)

ARQUIVO = "backend/app/repo/user.py"


def achado(
    linha: int,
    severidade: Severidade = Severidade.ERRO,
    caminho: str = ARQUIVO,
    categoria: str | None = None,
):
    return Achado(
        regra="python.lang.security.audit.sqli",
        severidade=severidade,
        caminho=caminho,
        linha_inicio=linha,
        linha_fim=linha,
        mensagem="possível SQL injection",
        categoria=categoria,
    )


def contexto(tocadas=None, tudo_novo=False):
    return Contexto(
        owner="gabhrielv",
        repo="hoppr",
        head_sha="a1b2c3",
        evento=Evento.PULL_REQUEST,
        linhas_tocadas=tocadas or {},
        numero_pr=7,
        tudo_novo=tudo_novo,
    )


def test_achado_novo_com_severidade_bloqueante_trava():
    v = decidir([achado(88)], contexto({ARQUIVO: (FaixaLinhas(80, 95),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO
    assert len(v.bloqueantes) == 1
    assert v.preexistentes == ()


def test_achado_em_linha_nao_tocada_e_preexistente_e_nao_trava():
    v = decidir([achado(88)], contexto({ARQUIVO: (FaixaLinhas(200, 210),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert v.bloqueantes == ()
    assert len(v.preexistentes) == 1


def test_arquivo_fora_do_diff_e_preexistente():
    v = decidir([achado(88)], contexto({"outro/arquivo.py": (FaixaLinhas(1, 50),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.preexistentes) == 1


def test_achado_novo_de_severidade_menor_vira_aviso_e_nao_trava():
    v = decidir(
        [achado(88, Severidade.AVISO)],
        contexto({ARQUIVO: (FaixaLinhas(80, 95),)}),
    )
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.avisos) == 1
    assert v.bloqueantes == ()


def test_sobreposicao_parcial_conta_como_novo():
    a = Achado(
        regra="r",
        severidade=Severidade.ERRO,
        caminho=ARQUIVO,
        linha_inicio=10,
        linha_fim=15,
        mensagem="m",
    )
    v = decidir([a], contexto({ARQUIVO: (FaixaLinhas(14, 20),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_tudo_novo_ignora_o_diff_e_trava():
    v = decidir([achado(88)], contexto({}, tudo_novo=True))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_sem_achados_libera():
    v = decidir([], contexto({ARQUIVO: (FaixaLinhas(1, 100),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert v.bloqueantes == ()
    assert v.avisos == ()
    assert v.preexistentes == ()


def test_modo_degradado_propaga_para_o_veredito():
    v = decidir(
        [achado(88)],
        contexto({ARQUIVO: (FaixaLinhas(80, 95),)}),
        degradado=True,
        motivo="cota do LLM esgotada",
    )
    assert v.degradado is True
    assert v.motivo == "cota do LLM esgotada"
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_veredito_carrega_a_versao_da_regra():
    v = decidir([], contexto())
    assert v.versao_regra == VERSAO_REGRA


def test_nao_conclui_nao_libera_e_carrega_o_motivo():
    v = nao_conclui("semgrep saiu com 2")
    assert v.estado is EstadoVeredito.NAO_CONCLUI
    assert v.motivo == "semgrep saiu com 2"
    assert v.bloqueantes == ()
    assert v.versao_regra == VERSAO_REGRA


def test_aviso_de_seguranca_bloqueia():
    a = achado(88, Severidade.AVISO, categoria="security")
    v = decidir([a], contexto({ARQUIVO: (FaixaLinhas(80, 95),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_aviso_de_performance_nao_bloqueia():
    a = achado(88, Severidade.AVISO, categoria="performance")
    v = decidir([a], contexto({ARQUIVO: (FaixaLinhas(80, 95),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.avisos) == 1


def test_erro_sem_categoria_declarada_continua_bloqueando():
    # Regra de terceiro sem metadados não pode fazer o portão falhar aberto.
    v = decidir([achado(88)], contexto({ARQUIVO: (FaixaLinhas(80, 95),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_achado_em_excecao_declarada_nao_bloqueia():
    a = Achado(
        regra="python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret",
        severidade=Severidade.ERRO,
        caminho="backend/tests/test_security.py",
        linha_inicio=278,
        linha_fim=278,
        mensagem="segredo fixo",
        categoria="security",
    )
    v = decidir([a], contexto({"backend/tests/test_security.py": (FaixaLinhas(270, 280),)}))
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.silenciados) == 1
    assert v.bloqueantes == ()


def test_excecao_nao_vale_para_outro_caminho():
    a = Achado(
        regra="python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret",
        severidade=Severidade.ERRO,
        caminho="backend/app/auth.py",
        linha_inicio=10,
        linha_fim=10,
        mensagem="segredo fixo",
        categoria="security",
    )
    v = decidir([a], contexto({"backend/app/auth.py": (FaixaLinhas(1, 50),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO
    assert v.silenciados == ()


def test_excecao_nao_vale_para_outra_regra():
    a = achado(278, caminho="backend/tests/test_security.py", categoria="security")
    v = decidir([a], contexto({"backend/tests/test_security.py": (FaixaLinhas(270, 280),)}))
    assert v.estado is EstadoVeredito.BLOQUEADO
