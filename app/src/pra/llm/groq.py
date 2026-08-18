"""Groq por HTTP, sem SDK.

Sem SDK de propósito: a API é compatível com a da OpenAI, o `requests` já está
no perfil `nuvem` e no zip, e uma dependência a menos é uma versão a menos para
prender.

**Groq não é Grok.** O da xAI passou a tratar prompt, input e output como
conteúdo de treino no nível grátis em 15/01/2026; usar ele violaria a restrição
que a D2b impõe e a D7 herda. Confira o nome antes de configurar o SSM.
"""

from __future__ import annotations

import json
import time

import requests

from pra.llm.cliente import (
    Chamada,
    CotaEsgotada,
    Ferramenta,
    ProvedorIndisponivel,
    RespostaLLM,
)

URL = "https://api.groq.com/openai/v1/chat/completions"
TEMPO_LIMITE_S = 60
TENTATIVAS = 3
ESPERA_BASE_S = 2
# A Lambda tem dez minutos no total. Dormir mais que isto dentro dela é queimar
# o orçamento da análise inteira para acordar e falhar do mesmo jeito.
ESPERA_MAX_S = 20

# A cota diária e o teto por minuto chegam os dois como 429, e só o segundo
# melhora com espera. A distinção sai do texto da mensagem, que é frágil — mas
# o erro cai para o lado seguro: sem reconhecer a marca, tenta de novo e
# degrada, que bloqueia igual.
MARCAS_DE_COTA_DIARIA = ("per day", "daily", "tokens per day")

LIMITE_MENSAGEM = 200


class ClienteGroq:
    def __init__(self, chave: str, modelo: str):
        self._chave = chave
        # Público de propósito: o nome do modelo vai para a evidência e daí
        # para a auditoria. A chave nunca sai daqui.
        self.modelo = modelo

    def conversar(
        self, mensagens: list[dict], ferramentas: tuple[Ferramenta, ...]
    ) -> RespostaLLM:
        corpo = {
            "model": self.modelo,
            "messages": mensagens,
            "tools": [_como_ferramenta(f) for f in ferramentas],
            # Investigação não é criatividade: a mesma pergunta tem que dar a
            # mesma resposta, senão o corpus mede ruído em vez do agente.
            "temperature": 0,
            # Amostragem gulosa não é o mesmo que provedor determinístico: em
            # lote, o roteamento e a redução em ponto flutuante dependem da
            # composição do batch. O `seed` é best-effort — reduz a divergência
            # e não substitui a repetição seletiva do `rodar.py`.
            "seed": 0,
        }

        ultimo = "sem resposta"
        for tentativa in range(TENTATIVAS):
            try:
                resposta = requests.post(
                    URL,
                    headers={"Authorization": f"Bearer {self._chave}"},
                    json=corpo,
                    timeout=TEMPO_LIMITE_S,
                )
            except requests.RequestException as erro:
                ultimo = f"{type(erro).__name__}"
                _esperar(tentativa, None)
                continue

            if resposta.status_code < 400:
                return _traduzir(resposta.json())

            ultimo = f"{resposta.status_code}: {_mensagem(resposta)}"

            if resposta.status_code == 429:
                if _e_cota_diaria(resposta):
                    raise CotaEsgotada(ultimo)
            elif resposta.status_code < 500:
                # 401, 400, 404: nenhum melhora com espera, e cada tentativa
                # custa tempo de Lambda.
                raise ProvedorIndisponivel(ultimo)

            _esperar(tentativa, resposta)

        raise ProvedorIndisponivel(f"desisti depois de {TENTATIVAS} tentativas — {ultimo}")


def _esperar(tentativa: int, resposta: requests.Response | None) -> None:
    if tentativa >= TENTATIVAS - 1:
        return

    espera = ESPERA_BASE_S * (2**tentativa)
    if resposta is not None:
        pedida = _retry_after(resposta)
        if pedida is not None:
            if pedida > ESPERA_MAX_S:
                raise ProvedorIndisponivel(
                    f"Retry-After de {pedida}s não cabe no orçamento da execução"
                )
            espera = pedida

    time.sleep(espera)


def _retry_after(resposta: requests.Response) -> float | None:
    bruto = resposta.headers.get("Retry-After")
    if not bruto:
        return None
    try:
        return float(bruto)
    except ValueError:
        # A forma em data HTTP existe no padrão e o Groq não usa. Ignorar cai
        # de volta na espera exponencial, que é seguro.
        return None


def _mensagem(resposta: requests.Response) -> str:
    """Nunca inclui a chave: isto sobe até o evidencias.json e a auditoria."""
    try:
        return str(resposta.json().get("error", {}).get("message", ""))[:LIMITE_MENSAGEM]
    except ValueError:
        return ""


def _e_cota_diaria(resposta: requests.Response) -> bool:
    texto = _mensagem(resposta).lower()
    return any(marca in texto for marca in MARCAS_DE_COTA_DIARIA)


def _como_ferramenta(ferramenta: Ferramenta) -> dict:
    return {
        "type": "function",
        "function": {
            "name": ferramenta.nome,
            "description": ferramenta.descricao,
            "parameters": ferramenta.parametros,
        },
    }


def _traduzir(dados: dict) -> RespostaLLM:
    mensagem = dados["choices"][0]["message"]
    chamadas = []
    for bruta in mensagem.get("tool_calls") or ():
        funcao = bruta["function"]
        try:
            argumentos = json.loads(funcao["arguments"])
        except (TypeError, ValueError):
            # Argumento que não parseia vira chamada sem argumento: a
            # ferramenta recusa, o loop segue e gasta um passo. Melhor que
            # derrubar a análise inteira por causa de uma vírgula.
            argumentos = {}
        if not isinstance(argumentos, dict):
            argumentos = {}
        chamadas.append(
            Chamada(nome=funcao["name"], argumentos=argumentos, id=bruta.get("id", ""))
        )

    return RespostaLLM(
        chamadas=tuple(chamadas),
        texto=mensagem.get("content") or "",
        tokens=int(dados.get("usage", {}).get("total_tokens", 0)),
    )
