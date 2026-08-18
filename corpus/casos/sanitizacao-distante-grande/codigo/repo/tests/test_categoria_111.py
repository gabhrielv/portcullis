from app.utils.categoria_111 import validar_categoria_111


def test_validar_categoria_111_remove_simbolo():
    assert validar_categoria_111("a!b") == "ab"


def test_validar_categoria_111_baixa_a_caixa():
    assert validar_categoria_111("AB") == "ab"
