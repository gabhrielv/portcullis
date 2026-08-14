import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from portcullis.github import auth
from portcullis.github.auth import TETO_GITHUB_S, jwt_do_app

APP_ID = "123456"


@pytest.fixture(scope="module")
def chaves():
    """Par RSA gerado no teste: nada de chave de verdade no repositório."""
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return pem, privada.public_key()


def decodificar(token: str, publica):
    return jwt.decode(token, publica, algorithms=["RS256"])


def test_token_e_assinado_pela_chave_privada_do_app(chaves):
    pem, publica = chaves
    assert decodificar(jwt_do_app(APP_ID, pem), publica)["iss"] == APP_ID


def test_token_usa_rs256(chaves):
    # O GitHub só aceita RS256. HS256 aqui seria assinar com a chave como
    # segredo simétrico — o GitHub recusaria e o erro não diria por quê.
    pem, _ = chaves
    assert jwt.get_unverified_header(jwt_do_app(APP_ID, pem))["alg"] == "RS256"


def test_iat_fica_no_passado_para_tolerar_relogio_adiantado(chaves):
    # Relógio da Lambda alguns segundos à frente do GitHub faria o token ser
    # recusado como "emitido no futuro".
    pem, publica = chaves
    assert decodificar(jwt_do_app(APP_ID, pem), publica)["iat"] < time.time()


def test_validade_cabe_no_teto_de_dez_minutos_do_github(chaves):
    pem, publica = chaves
    claims = decodificar(jwt_do_app(APP_ID, pem), publica)
    assert claims["exp"] - claims["iat"] <= TETO_GITHUB_S


def test_token_ainda_e_valido_agora(chaves):
    pem, publica = chaves
    assert decodificar(jwt_do_app(APP_ID, pem), publica)["exp"] > time.time()


def test_app_id_numerico_vira_string(chaves):
    # O App ID é um número na tela do GitHub, mas o claim `iss` é string.
    pem, publica = chaves
    assert decodificar(jwt_do_app(123456, pem), publica)["iss"] == APP_ID


class RespostaFalsa:
    def __init__(self, dados, codigo=200):
        self._dados = dados
        self.status_code = codigo

    def json(self):
        return self._dados

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class GithubFalso:
    """Registra as chamadas para o teste conferir o que foi pedido e como."""

    def __init__(self, codigo_instalacao=200):
        self.chamadas: list[tuple[str, str, dict]] = []
        self.codigo_instalacao = codigo_instalacao

    def get(self, url, headers=None, timeout=None):
        self.chamadas.append(("GET", url, headers or {}))
        return RespostaFalsa({"id": 153600764}, self.codigo_instalacao)

    def post(self, url, headers=None, timeout=None):
        self.chamadas.append(("POST", url, headers or {}))
        return RespostaFalsa({"token": "ghs_token_de_instalacao"})


@pytest.fixture
def github(monkeypatch):
    falso = GithubFalso()
    monkeypatch.setattr(auth, "requests", falso)
    return falso


def test_token_de_instalacao_devolve_o_token_emitido(chaves, github):
    pem, _ = chaves
    token = auth.token_de_instalacao(APP_ID, pem, "gabhrielv", "hoppr")
    assert token == "ghs_token_de_instalacao"


def test_token_e_pedido_para_a_instalacao_daquele_repositorio(chaves, github):
    # Token de instalação vale só onde o App foi instalado. Pedir pelo repo
    # certo é o que mantém o alcance restrito a ele.
    pem, _ = chaves
    auth.token_de_instalacao(APP_ID, pem, "gabhrielv", "hoppr")

    metodo, url, _ = github.chamadas[0]
    assert metodo == "GET"
    assert url.endswith("/repos/gabhrielv/hoppr/installation")


def test_as_duas_chamadas_usam_o_jwt_do_app(chaves, github):
    pem, publica = chaves
    auth.token_de_instalacao(APP_ID, pem, "gabhrielv", "hoppr")

    assert len(github.chamadas) == 2
    for _, _, cabecalhos in github.chamadas:
        enviado = cabecalhos["Authorization"].removeprefix("Bearer ")
        # Precisa ser o JWT do App, nao outra coisa: decodifica de verdade.
        assert decodificar(enviado, publica)["iss"] == APP_ID


def test_falha_ao_descobrir_a_instalacao_nao_vira_token_vazio(chaves, monkeypatch):
    # Se o App nao foi instalado no repositorio, isso precisa estourar aqui e
    # nao seguir adiante com token invalido.
    monkeypatch.setattr(auth, "requests", GithubFalso(codigo_instalacao=404))
    pem, _ = chaves
    with pytest.raises(RuntimeError):
        auth.token_de_instalacao(APP_ID, pem, "gabhrielv", "inexistente")


def test_chave_invalida_estoura_com_erro_de_chave(chaves):
    # Cenário real: colar o .pem errado no SSM. O erro precisa apontar para a
    # chave, não sair como um TypeError qualquer lá de dentro do PyJWT.
    with pytest.raises(ValueError):
        jwt_do_app(APP_ID, "isto-nao-e-uma-chave")
