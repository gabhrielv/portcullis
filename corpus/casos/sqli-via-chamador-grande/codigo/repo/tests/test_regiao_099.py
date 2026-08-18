from app.utils.regiao_099 import validar_regiao_099


def test_validar_regiao_099_remove_simbolo():
    assert validar_regiao_099("a!b") == "ab"


def test_validar_regiao_099_baixa_a_caixa():
    assert validar_regiao_099("AB") == "ab"
