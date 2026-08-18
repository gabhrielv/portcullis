from app.utils.regiao_019 import validar_regiao_019


def test_validar_regiao_019_remove_simbolo():
    assert validar_regiao_019("a!b") == "ab"


def test_validar_regiao_019_baixa_a_caixa():
    assert validar_regiao_019("AB") == "ab"
