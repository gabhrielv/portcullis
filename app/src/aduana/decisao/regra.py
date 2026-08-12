"""A regra determinística. Ver D6 e D15.

No marco 2 o agente entrega evidência ANTES desta função; ela continua sendo
quem decide. Nada aqui consulta rede.
"""

from __future__ import annotations

from collections.abc import Iterable

from aduana.decisao.excecoes import silenciado
from aduana.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Severidade,
    Veredito,
)

VERSAO_REGRA = "2"

CATEGORIA_SEGURANCA = "security"


def _bloqueia(achado: Achado) -> bool:
    # ERRO bloqueia sempre. AVISO só quando a regra se declara de segurança —
    # medido no hoppr em 12/08/2026: dos 12 avisos, 4 eram de performance.
    # Categoria ausente nunca promove, mas também nunca rebaixa um ERRO.
    if achado.severidade is Severidade.ERRO:
        return True
    return achado.severidade is Severidade.AVISO and achado.categoria == CATEGORIA_SEGURANCA


def _e_novo(achado: Achado, contexto: Contexto) -> bool:
    # Só linha ADICIONADA conta. PR que cria problema apagando linha passa:
    # limitação conhecida, documentada no README.
    if contexto.tudo_novo:
        return True
    faixas = contexto.linhas_tocadas.get(achado.caminho)
    if not faixas:
        return False
    return any(faixa.intersecta(achado.linha_inicio, achado.linha_fim) for faixa in faixas)


def decidir(
    achados: Iterable[Achado],
    contexto: Contexto,
    degradado: bool = False,
    motivo: str | None = None,
) -> Veredito:
    bloqueantes: list[Achado] = []
    avisos: list[Achado] = []
    preexistentes: list[Achado] = []
    silenciados: list[Achado] = []

    for achado in achados:
        if not _e_novo(achado, contexto):
            preexistentes.append(achado)
        elif silenciado(achado.regra, achado.caminho):
            silenciados.append(achado)
        elif _bloqueia(achado):
            bloqueantes.append(achado)
        else:
            avisos.append(achado)

    estado = EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO

    return Veredito(
        estado=estado,
        bloqueantes=tuple(bloqueantes),
        avisos=tuple(avisos),
        preexistentes=tuple(preexistentes),
        silenciados=tuple(silenciados),
        versao_regra=VERSAO_REGRA,
        degradado=degradado,
        motivo=motivo,
    )


def nao_conclui(motivo: str) -> Veredito:
    """Fail-closed explícito. Vira `action_required` no Check Run (D16)."""
    return Veredito(
        estado=EstadoVeredito.NAO_CONCLUI,
        bloqueantes=(),
        avisos=(),
        preexistentes=(),
        versao_regra=VERSAO_REGRA,
        motivo=motivo,
    )
