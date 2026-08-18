from app.utils.lote_075 import validar_lote_075


def test_validar_lote_075_remove_simbolo():
    assert validar_lote_075("a!b") == "ab"


def test_validar_lote_075_baixa_a_caixa():
    assert validar_lote_075("AB") == "ab"
