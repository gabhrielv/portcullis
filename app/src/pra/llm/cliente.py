"""O contrato com o provedor de modelo. Um método só, como manda a D7.

A interface existe porque a cota gratuita pode sumir — é requisito declarado,
não precaução. Trocar de provedor não pode tocar no loop do agente, e é por
isso que `agente/` depende de `llm/` e nunca o contrário.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Ferramenta:
    """O que o modelo pode pedir. `parametros` é JSON Schema."""

    nome: str
    descricao: str
    parametros: dict


@dataclass(frozen=True)
class Chamada:
    """`id` é o do provedor. Ele volta como `tool_call_id` no resultado, e a
    API recusa um `role: tool` que não case com nenhum `tool_calls`."""

    nome: str
    argumentos: dict
    id: str = ""


@dataclass(frozen=True)
class RespostaLLM:
    chamadas: tuple[Chamada, ...] = ()
    texto: str = ""
    tokens: int = 0


class CotaEsgotada(RuntimeError):
    """Não adianta tentar de novo hoje. Degrada para o modo marco 1 (D17)."""


class ProvedorIndisponivel(RuntimeError):
    """Falhou depois das tentativas com espera. Também degrada.

    Separada da CotaEsgotada porque as duas exigem respostas diferentes de
    quem opera: uma é esperar amanhã, a outra é olhar o provedor.
    """


class ClienteLLM(Protocol):
    # Quem julgou precisa ficar registrado junto com o julgamento: sem isto, a
    # auditoria não distingue mudança de modelo de mudança de prompt.
    modelo: str

    def conversar(
        self, mensagens: list[dict], ferramentas: tuple[Ferramenta, ...]
    ) -> RespostaLLM: ...
