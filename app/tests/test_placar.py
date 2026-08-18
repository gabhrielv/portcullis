"""A pontuação do corpus. Ela é o critério de aceite de qualquer mexida no
prompt ou no modelo — errar aqui reporta um número bonito sem avisar."""

from placar import evidencia_bate, linha_de_base, mede, render, resumir

from pra.modelos import Evidencia, Resposta


def evidencia(entrada="nao_sei", sanitizacao="nao_sei", prova=None, prova_valida=False):
    return Evidencia(
        chave="k",
        entrada_controlavel=Resposta(entrada),
        sanitizacao_encontrada=Resposta(sanitizacao),
        prova=prova,
        prova_valida=prova_valida,
        raciocinio="porque sim",
        passos=3,
        tokens=900,
    )


def test_campo_ausente_na_esperada_nao_e_conferido():
    """`{entrada_controlavel: sim}` aceita qualquer sanitizacao: o caso só tem
    opinião sobre a origem do valor."""
    aceitas = [{"entrada_controlavel": "sim"}]
    assert evidencia_bate(evidencia(entrada="sim", sanitizacao="nao"), aceitas)
    assert evidencia_bate(evidencia(entrada="sim", sanitizacao="sim"), aceitas)


def test_campo_presente_na_esperada_precisa_bater():
    aceitas = [{"entrada_controlavel": "sim", "sanitizacao_encontrada": "nao"}]
    assert not evidencia_bate(evidencia(entrada="sim", sanitizacao="sim"), aceitas)


def test_qualquer_uma_da_lista_basta():
    """`markup-com-inteiro` tem duas leituras honestas."""
    aceitas = [
        {"entrada_controlavel": "nao"},
        {"entrada_controlavel": "sim", "sanitizacao_encontrada": "sim", "prova_em": "app/x.py"},
    ]
    assert evidencia_bate(evidencia(entrada="nao"), aceitas)
    assert evidencia_bate(
        evidencia(entrada="sim", sanitizacao="sim", prova="app/x.py:4", prova_valida=True),
        aceitas,
    )


def test_prova_em_compara_o_arquivo_e_exige_prova_valida():
    aceitas = [{"sanitizacao_encontrada": "sim", "prova_em": "app/middleware.py"}]
    boa = evidencia(sanitizacao="sim", prova="app/middleware.py:7", prova_valida=True)
    outro_arquivo = evidencia(sanitizacao="sim", prova="app/outro.py:7", prova_valida=True)
    sem_conferir = evidencia(sanitizacao="sim", prova="app/middleware.py:7")
    assert evidencia_bate(boa, aceitas)
    assert not evidencia_bate(outro_arquivo, aceitas)
    assert not evidencia_bate(sem_conferir, aceitas)


def test_so_falso_positivo_e_armadilha_medem():
    """Nos vulneráveis comuns o portão já bloqueia por padrão: repetir custa
    cota e não mede nada."""
    assert mede({"gabarito": "FALSO_POSITIVO"})
    assert mede({"gabarito": "VULNERAVEL", "arma_falso_negativo": True})
    assert not mede({"gabarito": "VULNERAVEL"})


def _caso(gabarito="VULNERAVEL", **extra):
    return {"id": "x", "dificuldade": "media", "gabarito": gabarito, **extra}


def _exec(silenciou, bateu=True):
    return {"silenciou": silenciou, "raciocinio_bateu": bateu, "passos": 3, "tokens": 900}


def test_acertar_em_todas_as_execucoes_conta_como_acerto():
    linha = resumir(_caso(), [_exec(False), _exec(False)])
    assert linha["veredito_certo"] is True
    assert linha["estavel"] is True


def test_uma_execucao_errada_derruba_o_caso():
    """Média esconde: um portão que solta em 1 de 3 rodadas solta."""
    linha = resumir(_caso(), [_exec(False), _exec(True), _exec(False)])
    assert linha["veredito_certo"] is False
    assert linha["falso_negativo"] is True
    assert linha["estavel"] is False


def test_silenciar_falso_positivo_nao_e_falso_negativo():
    linha = resumir(_caso("FALSO_POSITIVO"), [_exec(True)])
    assert linha["veredito_certo"] is True
    assert linha["falso_negativo"] is False


def test_veredito_certo_com_raciocinio_errado_fica_registrado():
    """Bloqueou porque desistiu conta como veredito certo e raciocínio errado —
    é a distância entre as duas colunas que diz quanto do placar é sorte."""
    linha = resumir(_caso(), [_exec(False, bateu=False)])
    assert linha["veredito_certo"] is True
    assert linha["raciocinio_certo"] is False


def test_linha_de_base_e_o_agente_que_nao_silencia_nada():
    entradas = [
        _caso("VULNERAVEL"),
        _caso("VULNERAVEL", arma_falso_negativo=True),
        _caso("FALSO_POSITIVO"),
    ]
    base = linha_de_base(entradas)
    assert base["veredito"] == 2
    assert base["raciocinio"] == 0
    assert base["falso_negativos"] == 0
    assert base["ruido_removido"] == 0


def test_a_base_conta_o_caso_em_que_nao_sei_e_a_resposta_certa():
    """A base é derivada, não cravada. Se um gabarito passar a aceitar
    `nao_sei`, o agente nulo ganha aquele ponto — e a coluna `base` precisa
    dizer isso, senão o placar credita ao agente um acerto que era de graça."""
    entradas = [
        _caso("VULNERAVEL", evidencia_aceita=[{"entrada_controlavel": "sim"}]),
        _caso("VULNERAVEL", evidencia_aceita=[{"entrada_controlavel": "nao_sei"}]),
    ]
    assert linha_de_base(entradas)["raciocinio"] == 1


def test_falso_negativo_em_caso_obvio_entra_no_indice_do_corpus_todo():
    """Silenciar um vulnerável sem armadilha não move o índice das armadilhas.
    Se não houvesse a linha do corpus todo, o pior erro possível apareceria só
    como item de lista."""
    entradas = [
        _caso("VULNERAVEL", arma_falso_negativo=True),
        _caso("VULNERAVEL"),
    ]
    # silenciou o óbvio, acertou a armadilha
    linhas = [resumir(entradas[0], [_exec(False)]), resumir(entradas[1], [_exec(True)])]
    texto = " ".join(" ".join(x.split()) for x in render(linhas, entradas).splitlines())
    assert "falso-negativos 0/1" in texto
    assert "no corpus todo 1/2" in texto


def test_o_placar_mostra_a_coluna_da_linha_de_base():
    """Sem ela, `2/3` parece bom e esconde que o agente nulo já tirava 2."""
    entradas = [_caso("VULNERAVEL"), _caso("VULNERAVEL"), _caso("FALSO_POSITIVO")]
    linhas = [resumir(e, [_exec(e["gabarito"] == "FALSO_POSITIVO")]) for e in entradas]
    linhas_do_texto = [" ".join(x.split()) for x in render(linhas, entradas).splitlines()]
    assert "medido base" in linhas_do_texto
    assert "veredito 3/3 2/3" in linhas_do_texto
    assert any(x.startswith("raciocínio 3/3 0/3") for x in linhas_do_texto)
