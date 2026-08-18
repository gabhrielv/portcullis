from app.utils.lote_055 import validar_lote_055


def test_validar_lote_055_remove_simbolo():
    assert validar_lote_055("a!b") == "ab"


def test_validar_lote_055_baixa_a_caixa():
    assert validar_lote_055("AB") == "ab"
