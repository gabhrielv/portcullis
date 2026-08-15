"""A regra determinística. Ver D6 e D15.

No marco 2 o agente entrega evidência ANTES desta função; ela continua sendo
quem decide. Nada aqui consulta rede.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from portcullis.decisao.excecoes import silenciado
from portcullis.modelos import (
    Achado,
    Contexto,
    EstadoVeredito,
    Evidencia,
    Resposta,
    Severidade,
    Veredito,
    chave_do_achado,
)

VERSAO_REGRA = "3"

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


def silencia_por_evidencia(evidencia: Evidencia | None) -> bool:
    """A D6, sem folga. Pública porque o corpus mede exatamente esta função.

    Silenciar exige evidência POSITIVA e localizada. Ausência de evidência,
    `nao_sei`, ou prova que não aponta para lugar nenhum: tudo bloqueia. O
    único jeito de o portão afrouxar é alguém afrouxar isto aqui.
    """
    if evidencia is None:
        return False
    if evidencia.entrada_controlavel is Resposta.NAO:
        return True
    return evidencia.sanitizacao_encontrada is Resposta.SIM and evidencia.prova_valida


def decidir(
    achados: Iterable[Achado],
    contexto: Contexto,
    evidencias: Mapping[str, Evidencia] | None = None,
    degradado: bool = False,
    motivo: str | None = None,
) -> Veredito:
    bloqueantes: list[Achado] = []
    avisos: list[Achado] = []
    preexistentes: list[Achado] = []
    silenciados: list[Achado] = []
    por_evidencia: list[Achado] = []
    achadas = evidencias or {}

    for achado in achados:
        # A ordem das cláusulas é parte da decisão: a evidência só é
        # consultada depois de o achado já ser novo, não excetuado e de
        # severidade bloqueante. Consultá-la antes deixaria o agente alcançar
        # aviso e pré-existente, que ele não tem por que tocar.
        if not _e_novo(achado, contexto):
            preexistentes.append(achado)
        elif silenciado(achado.regra, achado.caminho):
            silenciados.append(achado)
        elif not _bloqueia(achado):
            avisos.append(achado)
        elif silencia_por_evidencia(achadas.get(chave_do_achado(achado))):
            por_evidencia.append(achado)
        else:
            bloqueantes.append(achado)

    estado = EstadoVeredito.BLOQUEADO if bloqueantes else EstadoVeredito.LIBERADO

    return Veredito(
        estado=estado,
        bloqueantes=tuple(bloqueantes),
        avisos=tuple(avisos),
        preexistentes=tuple(preexistentes),
        silenciados=tuple(silenciados),
        silenciados_por_evidencia=tuple(por_evidencia),
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
