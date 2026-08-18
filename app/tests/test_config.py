import pytest

from pra import config


class SsmFalso:
    """Dublê do cliente do SSM. Conta as chamadas e deixa trocar o valor."""

    def __init__(self, valor: str = "primeiro"):
        self.valor = valor
        self.chamadas = 0

    # PascalCase porque é a assinatura do boto3, não uma escolha.
    def get_parameter(self, Name: str, WithDecryption: bool):
        self.chamadas += 1
        return {"Parameter": {"Value": f"{self.valor}-{Name}"}}


@pytest.fixture
def ssm(monkeypatch):
    falso = SsmFalso()
    monkeypatch.setattr(config, "_cliente_ssm", lambda: falso)
    config.esquecer_parametros()
    return falso


def test_primeira_leitura_consulta_o_ssm(ssm):
    assert config.parametro_ssm("/x/y") == "primeiro-/x/y"
    assert ssm.chamadas == 1


def test_leitura_repetida_dentro_da_validade_nao_consulta_de_novo(ssm):
    config.parametro_ssm("/x/y")
    config.parametro_ssm("/x/y")
    config.parametro_ssm("/x/y")
    assert ssm.chamadas == 1


def test_valor_rotacionado_e_lido_depois_que_a_validade_expira(ssm, monkeypatch):
    # É o cenário que quebrou em produção: o segredo foi rotacionado nos dois
    # lados, e o container quente continuava conferindo contra o valor velho.
    assert config.parametro_ssm("/x/y") == "primeiro-/x/y"

    ssm.valor = "rotacionado"
    monkeypatch.setattr(config, "VALIDADE_CACHE_S", 0)

    assert config.parametro_ssm("/x/y") == "rotacionado-/x/y"
    assert ssm.chamadas == 2


def test_parametros_diferentes_nao_se_misturam(ssm):
    assert config.parametro_ssm("/a") == "primeiro-/a"
    assert config.parametro_ssm("/b") == "primeiro-/b"
    assert ssm.chamadas == 2


def test_esquecer_parametros_forca_nova_leitura(ssm):
    config.parametro_ssm("/x/y")
    config.esquecer_parametros()
    config.parametro_ssm("/x/y")
    assert ssm.chamadas == 2


def test_obrigatoria_recusa_variavel_ausente(monkeypatch):
    monkeypatch.delenv("PRA_INEXISTENTE", raising=False)
    with pytest.raises(RuntimeError):
        config.obrigatoria("PRA_INEXISTENTE")


def test_obrigatoria_trata_string_vazia_como_ausente(monkeypatch):
    monkeypatch.setenv("PRA_VAZIA", "")
    with pytest.raises(RuntimeError):
        config.obrigatoria("PRA_VAZIA")
