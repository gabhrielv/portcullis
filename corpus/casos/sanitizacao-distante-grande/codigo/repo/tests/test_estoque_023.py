from app.utils.estoque_023 import validar_estoque_023


def test_validar_estoque_023_remove_simbolo():
    assert validar_estoque_023("a!b") == "ab"


def test_validar_estoque_023_baixa_a_caixa():
    assert validar_estoque_023("AB") == "ab"
