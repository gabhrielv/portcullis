"""Autenticação do GitHub App.

Camada 1: o JWT assinado com a chave privada do App, que prova "sou o App
123456". Serve para falar sobre o App em si — inclusive `PATCH /app/hook/config`,
que é como a URL do webhook é corrigida depois de cada `terraform apply`.

A camada 2 (token de instalação, que abre tarball, diff e Check Run) nasce na
T8, junto com quem a consome.
"""

from __future__ import annotations

import time

import jwt

# O GitHub recusa token com validade maior que 10 minutos.
TETO_GITHUB_S = 600
# Relógio da Lambda adiantado faria o GitHub recusar o token como emitido no
# futuro. Recuar o `iat` é a recomendação da própria documentação.
FOLGA_RELOGIO_S = 60
DURACAO_S = 540


class ChavePrivadaInvalida(ValueError):
    pass


def jwt_do_app(app_id: str | int, chave_pem: str) -> str:
    agora = int(time.time()) - FOLGA_RELOGIO_S
    try:
        return jwt.encode(
            {"iat": agora, "exp": agora + DURACAO_S, "iss": str(app_id)},
            chave_pem,
            algorithm="RS256",
        )
    except (jwt.exceptions.InvalidKeyError, TypeError) as erro:
        # O PyJWT diz "could not parse the provided public key", que manda
        # procurar no lugar errado: o caso real é o .pem privado colado torto
        # no SSM.
        raise ChavePrivadaInvalida(
            f"chave privada do App não pôde ser lida: {erro}"
        ) from erro
