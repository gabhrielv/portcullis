from app.utils.cupom_007 import validar_cupom_007


def test_validar_cupom_007_remove_simbolo():
    assert validar_cupom_007("a!b") == "ab"


def test_validar_cupom_007_baixa_a_caixa():
    assert validar_cupom_007("AB") == "ab"
