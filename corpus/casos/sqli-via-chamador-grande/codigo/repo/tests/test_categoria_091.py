from app.utils.categoria_091 import validar_categoria_091


def test_validar_categoria_091_remove_simbolo():
    assert validar_categoria_091("a!b") == "ab"


def test_validar_categoria_091_baixa_a_caixa():
    assert validar_categoria_091("AB") == "ab"
