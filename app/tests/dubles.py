"""ClienteLLM falso e determinístico.

O agente inteiro é testado contra isto. Nenhum teste do `make teste` toca a
rede — é a G15, e é o que mantém a suíte em segundos.
"""

from __future__ import annotations

from portcullis.llm.cliente import Ferramenta, RespostaLLM


class ClienteFalso:
    """Devolve as respostas da lista, na ordem, e guarda o que recebeu."""

    def __init__(self, respostas: list[RespostaLLM]):
        self._respostas = list(respostas)
        self.conversas: list[list[dict]] = []

    def conversar(
        self, mensagens: list[dict], ferramentas: tuple[Ferramenta, ...]
    ) -> RespostaLLM:
        self.conversas.append(list(mensagens))
        if not self._respostas:
            # Loop que pede mais do que o teste previu é bug do loop, e o teste
            # precisa gritar em vez de repetir a última resposta para sempre.
            raise AssertionError("o loop pediu mais respostas do que o teste deu")
        return self._respostas.pop(0)


class ClienteQueFalha:
    def __init__(self, erro: Exception):
        self._erro = erro

    def conversar(
        self, mensagens: list[dict], ferramentas: tuple[Ferramenta, ...]
    ) -> RespostaLLM:
        raise self._erro
