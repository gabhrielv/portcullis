from app.utils.lote_095 import validar_lote_095


def test_validar_lote_095_remove_simbolo():
    assert validar_lote_095("a!b") == "ab"


def test_validar_lote_095_baixa_a_caixa():
    assert validar_lote_095("AB") == "ab"
