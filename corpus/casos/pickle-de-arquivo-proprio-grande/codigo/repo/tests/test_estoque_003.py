from app.utils.estoque_003 import validar_estoque_003


def test_validar_estoque_003_remove_simbolo():
    assert validar_estoque_003("a!b") == "ab"


def test_validar_estoque_003_baixa_a_caixa():
    assert validar_estoque_003("AB") == "ab"
