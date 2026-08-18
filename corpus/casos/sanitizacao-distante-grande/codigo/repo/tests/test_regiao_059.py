from app.utils.regiao_059 import validar_regiao_059


def test_validar_regiao_059_remove_simbolo():
    assert validar_regiao_059("a!b") == "ab"


def test_validar_regiao_059_baixa_a_caixa():
    assert validar_regiao_059("AB") == "ab"
