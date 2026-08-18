from app.utils.regiao_039 import validar_regiao_039


def test_validar_regiao_039_remove_simbolo():
    assert validar_regiao_039("a!b") == "ab"


def test_validar_regiao_039_baixa_a_caixa():
    assert validar_regiao_039("AB") == "ab"
