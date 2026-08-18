import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from pra.decisao.regra import (
    CWES_DE_FLUXO,
    CWES_FORA_DE_FLUXO,
    REGRAS_DE_FLUXO,
    VERSAO_REGRA,
    decidir,
    investigavel,
    nao_conclui,
)
from pra.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Evento,
    Evidencia,
    FaixaLinhas,
    Resposta,
    Severidade,
    chave_do_achado,
)

ARQUIVO = "backend/app/repo/user.py"


def achado(
    linha: int,
    severidade: Severidade = Severidade.ERRO,
    caminho: str = ARQUIVO,
    categoria: str | None = None,
    cwes: tuple[str, ...] = ("89",),
):
    return Achado(
        regra="python.lang.security.audit.sqli",
        severidade=severidade,
        caminho=caminho,
        linha_inicio=linha,
        linha_fim=linha,
        mensagem="possível SQL injection",
        categoria=categoria,
        cwes=cwes,
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


# ---------------------------------------------------------------------------
# Marco 2: a evidência do agente entra na decisão. Ver D6.
#
# A assimetria que governa tudo aqui: confiar no modelo para dizer "tem
# problema" é barato; confiar nele para dizer "não tem" é caro. Por isso
# silenciar exige evidência POSITIVA e localizada, e todo o resto bloqueia.
# ---------------------------------------------------------------------------

TOCADO = {ARQUIVO: (FaixaLinhas(80, 95),)}


def evidencia(
    alvo,
    entrada=Resposta.NAO_SEI,
    sanitizacao=Resposta.NAO_SEI,
    prova_valida=False,
):
    return {
        chave_do_achado(alvo): Evidencia(
            chave=chave_do_achado(alvo),
            entrada_controlavel=entrada,
            sanitizacao_encontrada=sanitizacao,
            prova="app/tipos.py:12" if prova_valida else None,
            prova_valida=prova_valida,
            raciocinio="o valor vem de um enum interno",
            passos=3,
            tokens=900,
        )
    }


def test_entrada_nao_controlavel_silencia():
    a = achado(88)
    v = decidir([a], contexto(TOCADO), evidencias=evidencia(a, entrada=Resposta.NAO))
    assert v.estado is EstadoVeredito.LIBERADO
    assert v.bloqueantes == ()
    assert len(v.silenciados_por_evidencia) == 1


def test_sanitizacao_com_prova_valida_silencia():
    a = achado(88)
    v = decidir(
        [a],
        contexto(TOCADO),
        evidencias=evidencia(a, sanitizacao=Resposta.SIM, prova_valida=True),
    )
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.silenciados_por_evidencia) == 1


def test_sanitizacao_sem_prova_valida_bloqueia():
    # "Achei sanitização" sem localização é exatamente o que uma injeção de
    # prompt produziria de mais barato.
    a = achado(88)
    v = decidir(
        [a],
        contexto(TOCADO),
        evidencias=evidencia(a, sanitizacao=Resposta.SIM, prova_valida=False),
    )
    assert v.estado is EstadoVeredito.BLOQUEADO
    assert len(v.bloqueantes) == 1


def test_nao_sei_nos_dois_campos_bloqueia():
    a = achado(88)
    assert decidir([a], contexto(TOCADO), evidencias=evidencia(a)).estado is (
        EstadoVeredito.BLOQUEADO
    )


def test_entrada_controlavel_sim_bloqueia():
    a = achado(88)
    v = decidir([a], contexto(TOCADO), evidencias=evidencia(a, entrada=Resposta.SIM))
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_achado_sem_evidencia_bloqueia():
    """Não investigado bloqueia: é o comportamento do marco 1, que a D17
    definiu como o modo degradado permanente."""
    assert decidir([achado(88)], contexto(TOCADO), evidencias={}).estado is (
        EstadoVeredito.BLOQUEADO
    )


def test_evidencia_ausente_e_o_mesmo_que_nao_passar_evidencia_nenhuma():
    sem = decidir([achado(88)], contexto(TOCADO))
    vazio = decidir([achado(88)], contexto(TOCADO), evidencias={})
    assert sem.estado is vazio.estado is EstadoVeredito.BLOQUEADO


def test_evidencia_de_outro_achado_nao_silencia():
    """A chave casa achado com evidência. Chave que não bate não pode virar
    silêncio — seria o jeito mais fácil de o portão falhar aberto."""
    v = decidir(
        [achado(88)],
        contexto(TOCADO),
        evidencias=evidencia(achado(200), entrada=Resposta.NAO),
    )
    assert v.estado is EstadoVeredito.BLOQUEADO


def test_evidencia_nao_promove_achado_preexistente():
    """O agente só silencia, nunca promove. Um achado fora do diff continua
    fora do diff mesmo com evidência dizendo que a entrada é controlável."""
    a = achado(88)
    v = decidir(
        [a],
        contexto({ARQUIVO: (FaixaLinhas(200, 210),)}),
        evidencias=evidencia(a, entrada=Resposta.SIM),
    )
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.preexistentes) == 1
    assert v.silenciados_por_evidencia == ()


def test_evidencia_nao_promove_aviso_a_bloqueante():
    a = achado(88, Severidade.AVISO, categoria="performance")
    v = decidir([a], contexto(TOCADO), evidencias=evidencia(a, entrada=Resposta.SIM))
    assert v.estado is EstadoVeredito.LIBERADO
    assert len(v.avisos) == 1


def test_excecao_declarada_e_evidencia_ficam_em_campos_separados():
    """Um é decisão de PESSOA, em excecoes.py; o outro é julgamento de MODELO.
    Juntar os dois apagaria a diferença no registro de auditoria (D11)."""
    a = achado(88)
    v = decidir([a], contexto(TOCADO), evidencias=evidencia(a, entrada=Resposta.NAO))
    assert v.silenciados == ()
    assert len(v.silenciados_por_evidencia) == 1


def test_excecao_declarada_vence_sem_gastar_evidencia():
    a = Achado(
        regra="python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret",
        severidade=Severidade.ERRO,
        caminho="backend/tests/test_security.py",
        linha_inicio=278,
        linha_fim=278,
        mensagem="segredo fixo",
        categoria="security",
    )
    v = decidir(
        [a],
        contexto({"backend/tests/test_security.py": (FaixaLinhas(270, 280),)}),
        evidencias=evidencia(a, entrada=Resposta.SIM),
    )
    assert len(v.silenciados) == 1
    assert v.silenciados_por_evidencia == ()


def test_versao_da_regra_subiu_para_quatro():
    """A v3 abriu a evidência; a v4 restringiu quais achados ela alcança. Sem
    subir a versão, o mesmo veredito viria de duas regras diferentes e a
    auditoria não teria como saber qual delas julgou."""
    assert VERSAO_REGRA == "4"


# ---------------------------------------------------------------------------
# Quais achados o agente chega a ver. As duas perguntas dele — de onde vem o
# valor, foi sanitizado — só fazem sentido para achado de FLUXO DE DADOS. Num
# segredo escrito no código não existe valor entrando: a resposta honesta a
# "isso vem de fora?" é "não", e "não" silencia. O agente acertaria a pergunta
# e deixaria passar a credencial.
# ---------------------------------------------------------------------------


def test_achado_de_fluxo_de_dados_e_investigavel():
    assert investigavel(achado(88, cwes=("89",))) is True


def test_credencial_no_codigo_nao_e_investigavel():
    """CWE-798 é `detected-aws-secret-access-key`. Sem valor entrando, a
    pergunta do agente não se aplica."""
    assert investigavel(achado(88, cwes=("798",))) is False


def test_cripto_fraca_nao_e_investigavel():
    assert investigavel(achado(88, cwes=("327",))) is False


def test_achado_sem_cwe_nao_e_investigavel():
    """Falha fechada: achado congelado antes deste campo existir bloqueia,
    nunca vira investigável por omissão."""
    assert investigavel(achado(88, cwes=())) is False


def test_um_cwe_de_fluxo_entre_varios_basta():
    assert investigavel(achado(88, cwes=("200", "89"))) is True


def test_evidencia_nao_silencia_achado_que_nao_e_de_fluxo():
    """É o caso `segredo-hardcoded`: mesmo com o agente respondendo que nada
    de fora controla aquela linha, a credencial continua bloqueando."""
    a = achado(88, cwes=("798",))
    v = decidir([a], contexto(TOCADO), evidencias=evidencia(a, entrada=Resposta.NAO))
    assert v.estado is EstadoVeredito.BLOQUEADO
    assert v.silenciados_por_evidencia == ()
    assert len(v.bloqueantes) == 1


def test_evidencia_com_prova_tambem_nao_alcanca_achado_fora_de_fluxo():
    a = achado(88, cwes=("798",))
    v = decidir(
        [a],
        contexto(TOCADO),
        evidencias=evidencia(a, sanitizacao=Resposta.SIM, prova_valida=True),
    )
    assert v.estado is EstadoVeredito.BLOQUEADO


# ---------------------------------------------------------------------------
# A lista de CWE decide quais achados o agente alcança, mas ela só vale se
# casar com o que as regras de verdade declaram. Estes dois testes são o que
# sobrou dos casos `segredo-hardcoded`, `segredo-em-fixture`, `senha-em-exemplo`
# e `hash-md5-senha`, que saíram do corpus em 18/08/2026: eles mediam o agente
# numa pergunta que não se aplica, e agora medem a lista.
# Marcados como integração porque leem `build/regras`, que o `make regras` baixa.
# ---------------------------------------------------------------------------

REGRAS_CONGELADAS = Path(__file__).resolve().parents[2] / "build" / "regras"


@cache
def _conjunto_congelado() -> dict[str, frozenset[str]]:
    """Os dois YAML somam ~1000 regras e parsear por teste levava minutos."""
    regras: dict[str, frozenset[str]] = {}
    for arquivo in sorted(REGRAS_CONGELADAS.glob("*.yaml")):
        for r in yaml.safe_load(arquivo.read_text()).get("rules", []):
            md = r.get("metadata") or {}
            bruto = md.get("cwe") or []
            if isinstance(bruto, str):
                bruto = [bruto]
            numeros = frozenset(
                m.group(1) for x in bruto if (m := re.match(r"CWE-(\d+)", str(x)))
            )
            regras[r["id"]] = numeros if md.get("category") == "security" else frozenset()
    return regras


def _cwes_da_regra(id_completo: str) -> set[str]:
    """Id completo, nunca sufixo. `tainted-sql-string` existe em sete
    linguagens no mesmo conjunto, com CWE diferente em cada uma: casar por
    sufixo pega a primeira e mede a regra errada."""
    regras = _conjunto_congelado()
    if id_completo not in regras:
        raise AssertionError(f"regra {id_completo} não está no conjunto congelado")
    return set(regras[id_completo])


def _regras_alvo_do_corpus() -> list[str]:
    gabarito = Path(__file__).resolve().parents[2] / "corpus" / "gabarito.yaml"
    return sorted({e["alvo"]["regra"] for e in yaml.safe_load(gabarito.read_text())})


@pytest.mark.integracao
@pytest.mark.parametrize("regra", _regras_alvo_do_corpus())
def test_toda_regra_alvo_do_corpus_e_investigavel(regra):
    """Sai do gabarito, não de uma lista à parte: caso novo entra neste teste
    sozinho, e alvo cuja regra deixou de ser investigável falha aqui em vez de
    virar um zero silencioso no placar."""
    assert investigavel(
        Achado(
            regra=regra,
            severidade=Severidade.ERRO,
            caminho="x.py",
            linha_inicio=1,
            linha_fim=1,
            mensagem="",
            cwes=tuple(_cwes_da_regra(regra)),
        )
    ), f"{regra} não é investigável"


@pytest.mark.integracao
@pytest.mark.parametrize(
    "regra",
    [
        "generic.secrets.security.detected-aws-secret-access-key.detected-aws-secret-access-key",
        "python.lang.security.audit.md5-used-as-password.md5-used-as-password",
    ],
)
def test_regra_fora_de_fluxo_nunca_alcanca_o_agente(regra):
    """Se um dia estas passarem a ser investigáveis, o agente volta a poder
    silenciar credencial no código respondendo `nao` — que é a resposta certa
    para a pergunta errada."""
    assert not investigavel(
        Achado(
            regra=regra,
            severidade=Severidade.ERRO,
            caminho="x.py",
            linha_inicio=1,
            linha_fim=1,
            mensagem="",
            cwes=tuple(_cwes_da_regra(regra)),
        )
    )


def _cwes_do_conjunto() -> set[str]:
    return set().union(*_conjunto_congelado().values())


@pytest.mark.integracao
def test_todo_cwe_do_conjunto_esta_classificado():
    """CWE novo quebra a build em vez de virar bloqueio silencioso.

    Sem isto, um `make regras` pode tirar uma família inteira do alcance do
    agente sem sinal nenhum. Foi exatamente assim que o CWE-79 ficou de fora da
    primeira versão da lista: `xss-render-sem-escape` e `markup-com-inteiro`
    teriam bloqueado para sempre, e o placar mostraria só um número pior.
    """
    classificados = CWES_DE_FLUXO | CWES_FORA_DE_FLUXO
    orfaos = sorted(_cwes_do_conjunto() - classificados, key=int)
    assert not orfaos, f"CWE sem classificação: {['CWE-' + c for c in orfaos]}"


def test_os_dois_conjuntos_de_cwe_nao_se_cruzam():
    assert not (CWES_DE_FLUXO & CWES_FORA_DE_FLUXO)


@pytest.mark.integracao
def test_toda_excecao_de_regra_existe_no_conjunto():
    """Exceção que aponta para regra inexistente é lixo que ninguém vê: ela
    nunca casa e a família volta a bloquear em silêncio."""
    ids = set(_conjunto_congelado())
    assert REGRAS_DE_FLUXO <= ids, f"não existem: {sorted(REGRAS_DE_FLUXO - ids)}"


@pytest.mark.integracao
def test_toda_excecao_de_regra_e_mesmo_necessaria():
    """Exceção que o CWE já cobriria é ruído: some quando o conjunto de regras
    corrigir a etiqueta, e o teste avisa."""
    for regra in REGRAS_DE_FLUXO:
        assert not (
            _cwes_da_regra(regra) & CWES_DE_FLUXO
        ), f"{regra} já é investigável pelo CWE — tire da exceção"
