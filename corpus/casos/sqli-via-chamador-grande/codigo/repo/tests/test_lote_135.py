from app.utils.lote_135 import validar_lote_135


def test_validar_lote_135_remove_simbolo():
    assert validar_lote_135("a!b") == "ab"


def test_validar_lote_135_baixa_a_caixa():
    assert validar_lote_135("AB") == "ab"
