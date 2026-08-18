from app.utils.categoria_031 import validar_categoria_031


def test_validar_categoria_031_remove_simbolo():
    assert validar_categoria_031("a!b") == "ab"


def test_validar_categoria_031_baixa_a_caixa():
    assert validar_categoria_031("AB") == "ab"
