"""Achados que o portão não bloqueia.

Mora no repositório do aduana, e não no repositório analisado: quem abre um PR
no alvo não alcança este arquivo. É a válvula de escape que substitui o
`# nosemgrep`, desligado de propósito em `analisador/semgrep.py`.

Escopo por repositório chega com o `.aduana.yml` da D18, no marco 4.
"""

from __future__ import annotations

# (regra, prefixo do caminho)
EXCECOES: tuple[tuple[str, str], ...] = (
    # Segredo falso dentro do teste que verifica a checagem de segredo.
    (
        "python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret",
        "backend/tests/",
    ),
)


def silenciado(regra: str, caminho: str) -> bool:
    return any(regra == alvo and caminho.startswith(prefixo) for alvo, prefixo in EXCECOES)
