from pra.decisao.regra import VERSAO_REGRA, decidir, nao_conclui
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


def test_versao_da_regra_subiu_para_tres():
    """A auditoria precisa distinguir veredito com evidência de veredito sem."""
    assert VERSAO_REGRA == "3"
