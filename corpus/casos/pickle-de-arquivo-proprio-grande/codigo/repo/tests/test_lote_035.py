from app.utils.lote_035 import validar_lote_035


def test_validar_lote_035_remove_simbolo():
    assert validar_lote_035("a!b") == "ab"


def test_validar_lote_035_baixa_a_caixa():
    assert validar_lote_035("AB") == "ab"
