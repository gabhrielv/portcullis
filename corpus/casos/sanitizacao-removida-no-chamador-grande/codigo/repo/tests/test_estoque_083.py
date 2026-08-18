from app.utils.estoque_083 import validar_estoque_083


def test_validar_estoque_083_remove_simbolo():
    assert validar_estoque_083("a!b") == "ab"


def test_validar_estoque_083_baixa_a_caixa():
    assert validar_estoque_083("AB") == "ab"
