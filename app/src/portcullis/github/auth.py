"""Autenticação do GitHub App, em duas camadas.

Camada 1, o JWT: assinado com a chave privada, prova "sou o App 123456". Serve
para falar sobre o App em si — inclusive `PATCH /app/hook/config`, que é como a
URL do webhook é corrigida depois de cada `terraform apply`.

Camada 2, o token de instalação: prova "sou o App agindo dentro deste
repositório". Dura 1 hora e vale só onde o App foi instalado. É ele que abre
tarball, diff e Check Run.

Quem carrega esses valores são as Lambdas de fora da VPC. O analisador NUNCA os
vê — é a separação de privilégio da D14, e o `test_arquitetura.py` a garante.
"""

from __future__ import annotations

import time

import jwt
import requests

API = "https://api.github.com"
TEMPO_LIMITE_S = 30

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


def token_de_instalacao(app_id: str | int, chave_pem: str, owner: str, repo: str) -> str:
    """Token com alcance daquele repositório, não da conta inteira."""
    cabecalhos = {
        "Authorization": f"Bearer {jwt_do_app(app_id, chave_pem)}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    instalacao = requests.get(
        f"{API}/repos/{owner}/{repo}/installation",
        headers=cabecalhos,
        timeout=TEMPO_LIMITE_S,
    )
    # Estoura aqui em vez de seguir com token inválido: App não instalado no
    # repositório é erro de configuração, e o erro precisa dizer isso.
    instalacao.raise_for_status()

    token = requests.post(
        f"{API}/app/installations/{instalacao.json()['id']}/access_tokens",
        headers=cabecalhos,
        timeout=TEMPO_LIMITE_S,
    )
    token.raise_for_status()
    return token.json()["token"]
