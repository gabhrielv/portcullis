from app.utils.estoque_103 import validar_estoque_103


def test_validar_estoque_103_remove_simbolo():
    assert validar_estoque_103("a!b") == "ab"


def test_validar_estoque_103_baixa_a_caixa():
    assert validar_estoque_103("AB") == "ab"
