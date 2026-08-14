"""Registro de auditoria. Precisa responder "por que esse deploy passou?".

Mesma tabela do lock de deduplicação, distinguidos pela chave de ordenação:
`lock#{sha}` é reserva de trabalho, `{sha}` é o veredito. Single-table design.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import cache

import boto3

from portcullis.modelos import Achado, Veredito


@cache
def _tabela(nome: str):
    return boto3.resource("dynamodb").Table(nome)


def _serializar(achado: Achado) -> dict:
    return {
        "regra": achado.regra,
        "severidade": achado.severidade.value,
        "categoria": achado.categoria,
        "caminho": achado.caminho,
        "linha_inicio": achado.linha_inicio,
        "linha_fim": achado.linha_fim,
    }


def gravar_auditoria(
    tabela: str, repo: str, sha: str, veredito: Veredito, hash_regras: str
) -> None:
    _tabela(tabela).put_item(
        Item={
            "repo": repo,
            "sha": sha,
            "veredito": veredito.estado.value,
            "versao_regra": veredito.versao_regra,
            # Sem a impressão digital das regras, mudança no conjunto seria
            # indistinguível de mudança no agente, no marco 2.
            "hash_regras": hash_regras,
            "degradado": veredito.degradado,
            "motivo": veredito.motivo,
            "bloqueantes": [_serializar(a) for a in veredito.bloqueantes],
            "avisos": [_serializar(a) for a in veredito.avisos],
            "preexistentes": [_serializar(a) for a in veredito.preexistentes],
            "silenciados": [_serializar(a) for a in veredito.silenciados],
            "horario": datetime.now(UTC).isoformat(),
        }
    )
