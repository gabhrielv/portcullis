from app.utils.estoque_143 import validar_estoque_143


def test_validar_estoque_143_remove_simbolo():
    assert validar_estoque_143("a!b") == "ab"


def test_validar_estoque_143_baixa_a_caixa():
    assert validar_estoque_143("AB") == "ab"
