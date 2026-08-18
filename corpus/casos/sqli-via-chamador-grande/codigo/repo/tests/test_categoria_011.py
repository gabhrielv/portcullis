from app.utils.categoria_011 import validar_categoria_011


def test_validar_categoria_011_remove_simbolo():
    assert validar_categoria_011("a!b") == "ab"


def test_validar_categoria_011_baixa_a_caixa():
    assert validar_categoria_011("AB") == "ab"
