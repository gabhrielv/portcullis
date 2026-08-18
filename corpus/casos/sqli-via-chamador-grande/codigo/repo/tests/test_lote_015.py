from app.utils.lote_015 import validar_lote_015


def test_validar_lote_015_remove_simbolo():
    assert validar_lote_015("a!b") == "ab"


def test_validar_lote_015_baixa_a_caixa():
    assert validar_lote_015("AB") == "ab"
