import pytest

from pra.buscador.github_api import (
    ARQUIVO_INTEIRO,
    LIMITE_ARQUIVOS_GITHUB,
    faixas_de_patch,
    mapear_arquivos,
)
from pra.modelos import FaixaLinhas

# Montado como lista para a linha de contexto vazia ser um espaço de verdade,
# como o GitHub manda, e não uma linha vazia que o editor poderia comer.
# As contagens dos cabeçalhos batem com o conteúdo: hunk malformado testaria
# uma coisa que a API nunca envia.
_LINHAS = [
    "@@ -10,4 +10,5 @@ def buscar(conn, ident):",
    " def buscar(conn, ident):",
    '-    return conn.execute("SELECT 1")',
    '+    q = "SELECT * FROM users WHERE id = " + ident',
    "+    return conn.execute(q)",
    " ",
    " def outra():",
    "@@ -40,3 +42,4 @@ def fim():",
    "     pass",
    "     mais()",
    "     outra()",
    "+MAIS = 1",
    "",
]
PATCH = "\n".join(_LINHAS)


def test_extrai_faixas_de_linhas_adicionadas():
    faixas = faixas_de_patch(PATCH)
    assert FaixaLinhas(11, 12) in faixas
    assert FaixaLinhas(45, 45) in faixas


def test_linha_removida_nao_conta():
    # A linha `-` some do arquivo novo; não há o que anotar nela.
    assert faixas_de_patch("@@ -1,2 +1,1 @@\n-antigo\n contexto\n") == ()


def test_patch_vazio_devolve_vazio():
    assert faixas_de_patch("") == ()


def test_faixas_adjacentes_sao_unidas():
    assert faixas_de_patch("@@ -1,0 +1,3 @@\n+a\n+b\n+c\n") == (FaixaLinhas(1, 3),)


def test_linhas_separadas_viram_faixas_separadas():
    patch = "@@ -1,5 +1,6 @@\n+a\n b\n c\n+d\n"
    assert faixas_de_patch(patch) == (FaixaLinhas(1, 1), FaixaLinhas(4, 4))


def test_marcador_de_sem_nova_linha_no_fim_nao_conta_como_adicionada():
    # `\\ No newline at end of file` começa com barra invertida, não com `+`,
    # mas aparece dentro do hunk e não pode deslocar a contagem.
    patch = "@@ -1,1 +1,1 @@\n-antigo\n+novo\n\\ No newline at end of file\n"
    assert faixas_de_patch(patch) == (FaixaLinhas(1, 1),)


def test_arquivo_sem_patch_conta_inteiro_como_tocado():
    # O GitHub omite `patch` em arquivo binário ou com diff grande demais. O
    # arquivo MUDOU — só não sabemos onde. Trata-lo como nao-tocado seria falhar
    # ABERTO: todo achado nele viraria "pré-existente" e não bloquearia.
    mapa = mapear_arquivos([{"filename": "grande.py", "status": "modified"}])
    assert mapa["grande.py"] == ARQUIVO_INTEIRO


def test_arquivo_removido_e_ignorado():
    # Não existe mais; não há achado possível nem linha para anotar.
    mapa = mapear_arquivos([{"filename": "sumiu.py", "status": "removed"}])
    assert mapa == {}


def test_arquivo_com_patch_usa_as_faixas_do_patch():
    mapa = mapear_arquivos(
        [{"filename": "a.py", "status": "modified", "patch": "@@ -1,0 +1,2 @@\n+x\n+y\n"}]
    )
    assert mapa["a.py"] == (FaixaLinhas(1, 2),)


def test_limite_do_github_e_o_documentado():
    # A API para de contar em 3000 arquivos. Nao e a nossa paginacao.
    assert LIMITE_ARQUIVOS_GITHUB == 3000


@pytest.mark.parametrize("status", ["added", "modified", "renamed", "changed"])
def test_arquivo_sem_patch_conta_inteiro_em_qualquer_status_vivo(status):
    mapa = mapear_arquivos([{"filename": "x.bin", "status": status}])
    assert mapa["x.bin"] == ARQUIVO_INTEIRO
