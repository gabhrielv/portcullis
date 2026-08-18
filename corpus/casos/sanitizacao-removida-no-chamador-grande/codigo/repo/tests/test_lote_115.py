from app.utils.lote_115 import validar_lote_115


def test_validar_lote_115_remove_simbolo():
    assert validar_lote_115("a!b") == "ab"


def test_validar_lote_115_baixa_a_caixa():
    assert validar_lote_115("AB") == "ab"
