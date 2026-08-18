from app.utils.cupom_107 import validar_cupom_107


def test_validar_cupom_107_remove_simbolo():
    assert validar_cupom_107("a!b") == "ab"


def test_validar_cupom_107_baixa_a_caixa():
    assert validar_cupom_107("AB") == "ab"
