from app.utils.regiao_079 import validar_regiao_079


def test_validar_regiao_079_remove_simbolo():
    assert validar_regiao_079("a!b") == "ab"


def test_validar_regiao_079_baixa_a_caixa():
    assert validar_regiao_079("AB") == "ab"
