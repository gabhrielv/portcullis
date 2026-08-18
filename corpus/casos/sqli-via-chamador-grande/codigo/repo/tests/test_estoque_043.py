from app.utils.estoque_043 import validar_estoque_043


def test_validar_estoque_043_remove_simbolo():
    assert validar_estoque_043("a!b") == "ab"


def test_validar_estoque_043_baixa_a_caixa():
    assert validar_estoque_043("AB") == "ab"
