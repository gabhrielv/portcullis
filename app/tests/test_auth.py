import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

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


def test_chave_invalida_estoura_com_erro_de_chave(chaves):
    # Cenário real: colar o .pem errado no SSM. O erro precisa apontar para a
    # chave, não sair como um TypeError qualquer lá de dentro do PyJWT.
    with pytest.raises(ValueError):
        jwt_do_app(APP_ID, "isto-nao-e-uma-chave")
