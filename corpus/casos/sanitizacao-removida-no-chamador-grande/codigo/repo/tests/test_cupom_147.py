from app.utils.cupom_147 import validar_cupom_147


def test_validar_cupom_147_remove_simbolo():
    assert validar_cupom_147("a!b") == "ab"


def test_validar_cupom_147_baixa_a_caixa():
    assert validar_cupom_147("AB") == "ab"
