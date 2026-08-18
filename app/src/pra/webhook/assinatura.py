"""Validação do HMAC que o GitHub manda em X-Hub-Signature-256.

É a única coisa que impede qualquer pessoa na internet de disparar análises na
conta da AWS. Sem isso, a URL do API Gateway é um botão público de gastar.
"""

from __future__ import annotations

import hashlib
import hmac

PREFIXO = "sha256="


def conferir_assinatura(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    if not cabecalho or not cabecalho.startswith(PREFIXO):
        return False

    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    # compare_digest evita ataque de temporização: comparar com == vaza, pelo
    # tempo de resposta, quantos bytes iniciais o atacante já acertou.
    return hmac.compare_digest(esperado, cabecalho[len(PREFIXO) :])
