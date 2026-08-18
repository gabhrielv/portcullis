from app.utils.categoria_071 import validar_categoria_071


def test_validar_categoria_071_remove_simbolo():
    assert validar_categoria_071("a!b") == "ab"


def test_validar_categoria_071_baixa_a_caixa():
    assert validar_categoria_071("AB") == "ab"
