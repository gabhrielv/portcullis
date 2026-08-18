from app.utils.regiao_139 import validar_regiao_139


def test_validar_regiao_139_remove_simbolo():
    assert validar_regiao_139("a!b") == "ab"


def test_validar_regiao_139_baixa_a_caixa():
    assert validar_regiao_139("AB") == "ab"
