"""O loop de investigação da D5, sob o orçamento da M2-4.

O agente decide o próximo passo com base no que acabou de ler — é isso que
separa isto de um pipeline com roteiro fixo.

Ele NUNCA emite veredito (G12): a saída é `Evidencia`, e quem julga é a
`regra.py`. Estourar o orçamento devolve `nao_sei`, que bloqueia (G13).
"""

from __future__ import annotations

import json
import logging

from portcullis.agente.ferramentas import Caixa
from portcullis.agente.prompt import FERRAMENTAS, SISTEMA, primeira_mensagem
from portcullis.llm.cliente import Chamada, ClienteLLM
from portcullis.modelos import Achado, Evidencia, Resposta, chave_do_achado

logger = logging.getLogger(__name__)

PASSOS_MAX = 8
# Folga de três vezes na janela de 128K. O teto existe para pegar o loop que
# empacou relendo arquivo grande, não para disputar espaço com o modelo.
TETO_TOKENS = 40_000

TETO_RACIOCINIO = 500


def _resposta(bruto) -> Resposta:
    """O modelo escreve o valor; o vocabulário é nosso. Fora dele, `nao_sei` —
    que bloqueia. Não existe valor desconhecido que libere."""
    try:
        return Resposta(str(bruto).strip().lower())
    except ValueError:
        return Resposta.NAO_SEI


def _sem_conclusao(achado: Achado, passos: int, tokens: int, motivo: str) -> Evidencia:
    return Evidencia(
        chave=chave_do_achado(achado),
        entrada_controlavel=Resposta.NAO_SEI,
        sanitizacao_encontrada=Resposta.NAO_SEI,
        raciocinio=motivo,
        passos=passos,
        tokens=tokens,
    )


def _executar(chamada: Chamada, caixa: Caixa) -> str:
    argumentos = chamada.argumentos
    if chamada.nome == "ler_arquivo":
        try:
            return caixa.ler_arquivo(
                str(argumentos.get("caminho", "")),
                inicio=argumentos.get("inicio"),
                fim=argumentos.get("fim"),
            )
        except ValueError as erro:
            return f"recusado: {erro}"
    if chamada.nome == "buscar":
        termos = argumentos.get("termos") or []
        return caixa.buscar(list(termos) if isinstance(termos, list) else [str(termos)])
    return f"ferramenta desconhecida: {chamada.nome}"


def _concluir(
    achado: Achado, chamada: Chamada, caixa: Caixa, passos: int, tokens: int
) -> Evidencia:
    argumentos = chamada.argumentos
    prova = argumentos.get("prova") or None
    return Evidencia(
        chave=chave_do_achado(achado),
        entrada_controlavel=_resposta(argumentos.get("entrada_controlavel")),
        sanitizacao_encontrada=_resposta(argumentos.get("sanitizacao_encontrada")),
        prova=prova,
        prova_valida=caixa.prova_valida(prova) if prova else False,
        raciocinio=str(argumentos.get("raciocinio") or "")[:TETO_RACIOCINIO],
        passos=passos,
        tokens=tokens,
    )


def investigar(achado: Achado, caixa: Caixa, cliente: ClienteLLM) -> Evidencia:
    mensagens = [
        {"role": "system", "content": SISTEMA},
        {
            "role": "user",
            "content": primeira_mensagem(
                achado, caixa.janela(achado.caminho, achado.linha_inicio)
            ),
        },
    ]

    tokens = 0
    for passo in range(1, PASSOS_MAX + 1):
        resposta = cliente.conversar(mensagens, FERRAMENTAS)
        tokens += resposta.tokens

        if not resposta.chamadas:
            # Texto solto não é evidência. Empurra de volta para o formato uma
            # vez; se insistir, o orçamento acaba e vira nao_sei.
            mensagens.append({"role": "assistant", "content": resposta.texto})
            mensagens.append(
                {"role": "user", "content": "Use uma ferramenta ou chame concluir."}
            )
            continue

        chamada = resposta.chamadas[0]
        if chamada.nome == "concluir":
            return _concluir(achado, chamada, caixa, passo, tokens)

        saida = _executar(chamada, caixa)
        mensagens.append(
            {
                "role": "assistant",
                "content": f"[{chamada.nome} {json.dumps(chamada.argumentos)}]",
            }
        )
        mensagens.append({"role": "user", "content": saida})

        if tokens > TETO_TOKENS:
            logger.warning("teto de tokens estourado no passo %s: %s", passo, tokens)
            return _sem_conclusao(achado, passo, tokens, "teto de tokens estourado")

    logger.warning("orçamento de passos estourado: %s tokens", tokens)
    return _sem_conclusao(achado, PASSOS_MAX, tokens, "orçamento de passos estourado")
