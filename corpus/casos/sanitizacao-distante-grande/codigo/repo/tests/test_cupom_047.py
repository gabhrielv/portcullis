from app.utils.cupom_047 import validar_cupom_047


def test_validar_cupom_047_remove_simbolo():
    assert validar_cupom_047("a!b") == "ab"


def test_validar_cupom_047_baixa_a_caixa():
    assert validar_cupom_047("AB") == "ab"
