from app.utils.cupom_067 import validar_cupom_067


def test_validar_cupom_067_remove_simbolo():
    assert validar_cupom_067("a!b") == "ab"


def test_validar_cupom_067_baixa_a_caixa():
    assert validar_cupom_067("AB") == "ab"
