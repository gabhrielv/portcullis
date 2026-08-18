from app.utils.cupom_127 import validar_cupom_127


def test_validar_cupom_127_remove_simbolo():
    assert validar_cupom_127("a!b") == "ab"


def test_validar_cupom_127_baixa_a_caixa():
    assert validar_cupom_127("AB") == "ab"
