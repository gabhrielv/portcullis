from app.utils.estoque_123 import validar_estoque_123


def test_validar_estoque_123_remove_simbolo():
    assert validar_estoque_123("a!b") == "ab"


def test_validar_estoque_123_baixa_a_caixa():
    assert validar_estoque_123("AB") == "ab"
