from portcullis.decisao.regra import VERSAO_REGRA
from portcullis.github.checks import LIMITE_ANOTACOES, montar_saida
from portcullis.modelos import Achado, EstadoVeredito, Severidade, Veredito


def achado(n: int, severidade=Severidade.ERRO, categoria="security"):
    return Achado("regra.x", severidade, f"a{n}.py", n, n, f"achado {n}", categoria)


def veredito(
    bloqueantes=(), avisos=(), preexistentes=(), silenciados=(), estado=None, **kw
):
    return Veredito(
        estado=estado
        or (EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO),
        bloqueantes=bloqueantes,
        avisos=avisos,
        preexistentes=preexistentes,
        silenciados=silenciados,
        versao_regra=VERSAO_REGRA,
        **kw,
    )


def test_bloqueado_vira_failure():
    saida = montar_saida(veredito(bloqueantes=(achado(1),)))
    assert saida["conclusion"] == "failure"
    assert "1 achado" in saida["output"]["title"]


def test_liberado_vira_success():
    assert montar_saida(veredito())["conclusion"] == "success"


def test_nao_conclui_vira_action_required():
    # Distinguir "achei algo" de "nao consegui concluir" muda o que o dev faz.
    v = veredito(estado=EstadoVeredito.NAO_CONCLUI, motivo="semgrep saiu com 2")
    saida = montar_saida(v)
    assert saida["conclusion"] == "action_required"
    assert "semgrep" in saida["output"]["title"]


def test_apenas_achado_novo_vira_anotacao():
    # Anotacao so renderiza inline em linha que o diff tocou. Pre-existente em
    # arquivo nao tocado nao apareceria em lugar nenhum — vai para o resumo.
    saida = montar_saida(
        veredito(
            bloqueantes=(achado(1),), avisos=(achado(2),), preexistentes=(achado(3),)
        )
    )
    caminhos = {a["path"] for a in saida["output"]["annotations"]}
    assert caminhos == {"a1.py", "a2.py"}


def test_niveis_de_anotacao_separam_bloqueante_de_aviso():
    saida = montar_saida(veredito(bloqueantes=(achado(1),), avisos=(achado(2),)))
    niveis = {a["path"]: a["annotation_level"] for a in saida["output"]["annotations"]}
    assert niveis["a1.py"] == "failure"
    assert niveis["a2.py"] == "warning"


def test_trunca_no_limite_da_api_e_diz_quanto_ficou_de_fora():
    bloqueantes = tuple(achado(n) for n in range(1, 74))
    saida = montar_saida(veredito(bloqueantes=bloqueantes))
    assert len(saida["output"]["annotations"]) == LIMITE_ANOTACOES
    assert "50 de 73" in saida["output"]["summary"]


def test_preexistentes_aparecem_no_resumo():
    saida = montar_saida(veredito(preexistentes=(achado(9),)))
    assert "pré-existente" in saida["output"]["summary"]
    assert "a9.py" in saida["output"]["summary"]


def test_silenciado_aparece_no_resumo_e_nunca_some():
    # A lista de excecoes substitui o `# nosemgrep`, que foi desligado. Se o
    # achado silenciado sumisse, silenciar viraria esconder.
    saida = montar_saida(veredito(silenciados=(achado(5),)))
    assert "silenciado" in saida["output"]["summary"].lower()
    assert "a5.py" in saida["output"]["summary"]


def test_silenciado_nao_bloqueia_e_nao_vira_anotacao():
    saida = montar_saida(veredito(silenciados=(achado(5),)))
    assert saida["conclusion"] == "success"
    assert saida["output"]["annotations"] == []


def test_modo_degradado_aparece_no_titulo():
    saida = montar_saida(veredito(bloqueantes=(achado(1),), degradado=True))
    assert "degradado" in saida["output"]["title"]


def test_resumo_carrega_a_versao_da_regra():
    # A auditoria precisa responder QUAL regra liberou aquele deploy.
    assert f"v{VERSAO_REGRA}" in montar_saida(veredito())["output"]["summary"]


def test_titulo_nao_carrega_texto_vindo_do_repositorio_analisado():
    # A mensagem do achado vem do semgrep, mas o caminho e o nome da regra
    # vem do repositorio. Titulo curto e fixo evita virar canal de texto.
    saida = montar_saida(veredito(bloqueantes=(achado(1),)))
    assert len(saida["output"]["title"]) <= 120
