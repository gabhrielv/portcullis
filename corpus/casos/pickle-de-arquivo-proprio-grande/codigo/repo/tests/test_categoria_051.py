from app.utils.categoria_051 import validar_categoria_051


def test_validar_categoria_051_remove_simbolo():
    assert validar_categoria_051("a!b") == "ab"


def test_validar_categoria_051_baixa_a_caixa():
    assert validar_categoria_051("AB") == "ab"
