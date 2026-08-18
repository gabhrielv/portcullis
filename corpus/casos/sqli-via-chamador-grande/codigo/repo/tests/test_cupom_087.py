from app.utils.cupom_087 import validar_cupom_087


def test_validar_cupom_087_remove_simbolo():
    assert validar_cupom_087("a!b") == "ab"


def test_validar_cupom_087_baixa_a_caixa():
    assert validar_cupom_087("AB") == "ab"
