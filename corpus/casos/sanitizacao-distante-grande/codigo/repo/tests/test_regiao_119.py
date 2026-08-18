from app.utils.regiao_119 import validar_regiao_119


def test_validar_regiao_119_remove_simbolo():
    assert validar_regiao_119("a!b") == "ab"


def test_validar_regiao_119_baixa_a_caixa():
    assert validar_regiao_119("AB") == "ab"
