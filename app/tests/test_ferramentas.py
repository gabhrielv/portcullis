"""O harness é a sala onde o agente trabalha. Isto tranca as portas dela.

Estes testes valem mais que os do loop: o loop erra e devolve `nao_sei`, que
bloqueia. Uma ferramenta que escapa da raiz entrega arquivo do host para um
modelo que acabou de ler código de terceiro.
"""

import pytest

from portcullis.agente.ferramentas import (
    LINHAS_DE_JANELA,
    TETO_LINHAS,
    TETO_RESULTADOS,
    Caixa,
)


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "rotas.py").write_text(
        "from app.db import por_id\n"
        "\n"
        "\n"
        "def ver(pedido):\n"
        "    return por_id(pedido['id'])\n"
    )
    (tmp_path / "app" / "db.py").write_text(
        "def por_id(identificador):\n    return identificador\n"
    )
    return tmp_path


# --- ler_arquivo -----------------------------------------------------------


def test_le_arquivo_inteiro(raiz):
    assert "def por_id" in Caixa(raiz).ler_arquivo("app/db.py")


def test_a_saida_traz_numero_de_linha(raiz):
    # Sem número, o modelo não consegue montar uma prova `arquivo:linha`, e a
    # prova é o que a D6 exige para silenciar.
    assert "1: def por_id" in Caixa(raiz).ler_arquivo("app/db.py")


def test_le_faixa_de_linhas(raiz):
    texto = Caixa(raiz).ler_arquivo("app/rotas.py", inicio=4, fim=5)
    assert "def ver" in texto
    assert "from app.db" not in texto


def test_recusa_escapar_da_raiz_com_ponto_ponto(raiz):
    with pytest.raises(ValueError):
        Caixa(raiz).ler_arquivo("../../etc/passwd")


def test_recusa_caminho_absoluto(raiz):
    with pytest.raises(ValueError):
        Caixa(raiz).ler_arquivo("/etc/passwd")


def test_recusa_symlink_que_aponta_para_fora(raiz, tmp_path_factory):
    fora = tmp_path_factory.mktemp("fora") / "segredo.txt"
    fora.write_text("credencial do host")
    (raiz / "atalho.py").symlink_to(fora)
    with pytest.raises(ValueError):
        Caixa(raiz).ler_arquivo("atalho.py")


def test_arquivo_inexistente_devolve_erro_e_nao_explode(raiz):
    # Caminho errado é o erro mais comum do modelo, e não pode custar a
    # análise: vira texto, o loop segue e gasta um passo.
    assert "não encontrei" in Caixa(raiz).ler_arquivo("app/nao_existe.py")


def test_pasta_nao_e_lida_como_arquivo(raiz):
    assert "não encontrei" in Caixa(raiz).ler_arquivo("app")


def test_leitura_para_no_teto_de_linhas(raiz):
    (raiz / "grande.py").write_text("x = 1\n" * (TETO_LINHAS + 500))
    texto = Caixa(raiz).ler_arquivo("grande.py")
    assert len(texto.splitlines()) <= TETO_LINHAS + 3
    assert "truncado" in texto


def test_arquivo_binario_nao_derruba_a_leitura(raiz):
    (raiz / "dados.bin").write_bytes(b"\xff\xfe\x00\x01")
    assert Caixa(raiz).ler_arquivo("dados.bin")


# --- janela ----------------------------------------------------------------


def test_janela_traz_o_contexto_em_volta_da_linha(raiz):
    assert "def ver" in Caixa(raiz).janela("app/rotas.py", 4)


def test_janela_perto_do_topo_nao_pede_linha_negativa(raiz):
    janela = Caixa(raiz).janela("app/db.py", 1)
    assert "1: def por_id" in janela


def test_janela_cobre_o_tamanho_pedido(raiz):
    (raiz / "medio.py").write_text("".join(f"linha{n}\n" for n in range(1, 101)))
    janela = Caixa(raiz).janela("medio.py", 50)
    assert f"{50 - LINHAS_DE_JANELA}: linha{50 - LINHAS_DE_JANELA}" in janela
    assert f"{50 + LINHAS_DE_JANELA}: linha{50 + LINHAS_DE_JANELA}" in janela


# --- buscar ----------------------------------------------------------------


def test_busca_acha_chamador(raiz):
    saida = Caixa(raiz).buscar(["por_id"])
    assert "app/rotas.py" in saida
    assert "app/db.py" in saida


def test_busca_aceita_varios_termos_de_uma_vez(raiz):
    # A união num passo só é o motivo de a ferramenta receber lista: cada
    # chamada custa um dos 8 passos do orçamento.
    saida = Caixa(raiz).buscar(["por_id", "def ver"])
    assert "app/rotas.py" in saida


def test_busca_sem_resultado_diz_que_nao_achou(raiz):
    assert "nenhuma" in Caixa(raiz).buscar(["coisa_que_nao_existe"]).lower()


def test_busca_para_no_teto_de_resultados(raiz):
    (raiz / "muitos.py").write_text("alvo = 1\n" * (TETO_RESULTADOS + 100))
    saida = Caixa(raiz).buscar(["alvo"])
    assert len(saida.splitlines()) <= TETO_RESULTADOS + 2


def test_busca_e_literal_e_nao_regex(raiz):
    """Se fosse regex, quem a escreve é o modelo — e o modelo acabou de ler
    código de quem abriu o PR. Um `(a+)+$` prende a Lambda até o timeout."""
    (raiz / "pontos.py").write_text("a.b.c = 1\naXbXc = 2\n")
    saida = Caixa(raiz).buscar(["a.b.c"])
    assert "a.b.c" in saida
    assert "aXbXc" not in saida


def test_busca_com_lista_vazia_nao_varre_tudo(raiz):
    assert "nenhuma" in Caixa(raiz).buscar([]).lower()


def test_busca_ignora_termo_que_nao_e_texto(raiz):
    assert "nenhuma" in Caixa(raiz).buscar([None, "", "   "]).lower()


def test_busca_nao_sai_da_raiz(raiz, tmp_path_factory):
    fora = tmp_path_factory.mktemp("fora") / "segredo.py"
    fora.write_text("por_id = 'credencial do host'\n")
    assert str(fora) not in Caixa(raiz).buscar(["por_id"])


def test_busca_ignora_binario(raiz):
    (raiz / "imagem.png").write_bytes(b"\x89PNG\r\n" + b"por_id" * 10)
    assert "imagem.png" not in Caixa(raiz).buscar(["por_id"])


# --- prova_valida ----------------------------------------------------------


def test_prova_valida_confere_arquivo_e_linha(raiz):
    caixa = Caixa(raiz)
    assert caixa.prova_valida("app/db.py:1") is True
    assert caixa.prova_valida("app/db.py:2") is True


def test_prova_em_faixa_de_linhas_vale(raiz):
    """Sanitização que ocupa duas linhas — o `if` e o `abort` — é citada assim.

    Recusar por formato descartava prova CORRETA: medido no
    `sanitizacao-distante`, onde o endereço apontava para o lugar certo e o
    acerto virou erro.
    """
    assert Caixa(raiz).prova_valida("app/db.py:1-2") is True


def test_faixa_que_estoura_o_arquivo_nao_vale(raiz):
    """Aceitar faixa não pode virar porta para endereço inventado."""
    caixa = Caixa(raiz)
    assert caixa.prova_valida("app/db.py:1-9999") is False
    assert caixa.prova_valida("app/db.py:0-2") is False


def test_faixa_malformada_nao_vale(raiz):
    caixa = Caixa(raiz)
    assert caixa.prova_valida("app/db.py:1-2-3") is False
    assert caixa.prova_valida("app/db.py:1-") is False
    assert caixa.prova_valida("app/db.py:-2") is False


def test_prova_com_linha_alem_do_fim_do_arquivo_nao_vale(raiz):
    assert Caixa(raiz).prova_valida("app/db.py:9999") is False


def test_prova_de_arquivo_inventado_nao_vale(raiz):
    # É a mentira mais barata que uma injeção de prompt produz: afirmar
    # sanitização e apontar para um arquivo que não existe.
    assert Caixa(raiz).prova_valida("app/middleware_que_nao_existe.py:12") is False


def test_prova_malformada_nao_vale(raiz):
    caixa = Caixa(raiz)
    assert caixa.prova_valida("sem dois pontos") is False
    assert caixa.prova_valida("app/db.py:abc") is False
    assert caixa.prova_valida("app/db.py:0") is False
    assert caixa.prova_valida("") is False


def test_prova_nao_pode_apontar_para_fora_da_raiz(raiz):
    assert Caixa(raiz).prova_valida("../../etc/passwd:1") is False
