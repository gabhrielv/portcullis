from app.utils.categoria_131 import validar_categoria_131


def test_validar_categoria_131_remove_simbolo():
    assert validar_categoria_131("a!b") == "ab"


def test_validar_categoria_131_baixa_a_caixa():
    assert validar_categoria_131("AB") == "ab"
