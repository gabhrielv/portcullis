from app.utils.estoque_063 import validar_estoque_063


def test_validar_estoque_063_remove_simbolo():
    assert validar_estoque_063("a!b") == "ab"


def test_validar_estoque_063_baixa_a_caixa():
    assert validar_estoque_063("AB") == "ab"
