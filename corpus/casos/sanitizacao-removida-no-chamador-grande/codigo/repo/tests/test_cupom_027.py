from app.utils.cupom_027 import validar_cupom_027


def test_validar_cupom_027_remove_simbolo():
    assert validar_cupom_027("a!b") == "ab"


def test_validar_cupom_027_baixa_a_caixa():
    assert validar_cupom_027("AB") == "ab"
