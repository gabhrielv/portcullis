"""Lista os modelos do provedor e mede o que a D7 deixou por confirmar.

A D7 fechou o provedor (Groq) e deixou duas perguntas em aberto sobre o modelo
específico: **o rate limit dele serve?** e **ele faz tool calling confiável?**.
O harness da §3 depende de tool calling — sem ele, o loop não tem como pedir
`ler_arquivo` nem `buscar`, e o marco 2 não existe.

Escolher por reputação seria repetir o erro da D7 com a Cerebras: olhar um
número (cota/dia) e não olhar o que quebrava (janela de contexto).

A chave sai do SSM, nunca do ambiente nem do código — G2.

Uso:
    .venv/bin/python scripts/sondar_modelo.py
    .venv/bin/python scripts/sondar_modelo.py --modelo nome-exato
"""

from __future__ import annotations

import argparse
import sys

import requests

from pra.config import parametro_ssm
from pra.llm.cliente import Ferramenta
from pra.llm.groq import URL, ClienteGroq

PARAMETRO_CHAVE = "/pra/llm/chave"
URL_MODELOS = "https://api.groq.com/openai/v1/models"
TEMPO_LIMITE_S = 30

# Uma pergunta que só se responde usando a ferramenta. Se o modelo responder
# em texto, ele não serve — o loop inteiro depende de ele PEDIR a ferramenta.
FERRAMENTA_DE_TESTE = Ferramenta(
    nome="ler_arquivo",
    descricao="Lê um arquivo do repositório.",
    parametros={
        "type": "object",
        "properties": {"caminho": {"type": "string"}},
        "required": ["caminho"],
    },
)
PERGUNTA = [
    {
        "role": "system",
        "content": "Você investiga código. Use as ferramentas antes de responder.",
    },
    {
        "role": "user",
        "content": "O que tem no arquivo app/db.py? Leia antes de responder.",
    },
]


def listar_modelos(chave: str) -> list[str]:
    resposta = requests.get(
        URL_MODELOS,
        headers={"Authorization": f"Bearer {chave}"},
        timeout=TEMPO_LIMITE_S,
    )
    resposta.raise_for_status()
    return sorted(m["id"] for m in resposta.json().get("data", []))


def limites(chave: str, modelo: str) -> dict:
    """Os limites vêm em cabeçalho, e só numa resposta de verdade."""
    resposta = requests.post(
        URL,
        headers={"Authorization": f"Bearer {chave}"},
        json={"model": modelo, "messages": [{"role": "user", "content": "oi"}], "max_tokens": 1},
        timeout=TEMPO_LIMITE_S,
    )
    return {
        chave_cab.replace("x-ratelimit-", ""): valor
        for chave_cab, valor in resposta.headers.items()
        if chave_cab.lower().startswith("x-ratelimit")
    }


def testar_tool_calling(chave: str, modelo: str) -> tuple[bool, str]:
    try:
        resposta = ClienteGroq(chave, modelo).conversar(PERGUNTA, (FERRAMENTA_DE_TESTE,))
    except Exception as falha:  # noqa: BLE001 — sonda: qualquer falha é resultado
        return False, f"{type(falha).__name__}: {falha}"

    if not resposta.chamadas:
        return False, f"respondeu em texto: {resposta.texto[:80]!r}"
    chamada = resposta.chamadas[0]
    if chamada.nome != "ler_arquivo":
        return False, f"chamou {chamada.nome!r}, que não existe"
    if "caminho" not in chamada.argumentos:
        return False, f"chamou sem o argumento obrigatório: {chamada.argumentos}"
    return True, f"pediu ler_arquivo({chamada.argumentos['caminho']!r})"


def principal(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--modelo", help="sonda só este; sem isto, lista todos")
    argumentos = analisador.parse_args(argv)

    chave = parametro_ssm(PARAMETRO_CHAVE)

    if not argumentos.modelo:
        print("modelos disponíveis:\n")
        for nome in listar_modelos(chave):
            print(f"  {nome}")
        print("\nsonde um com: --modelo <nome>")
        return 0

    modelo = argumentos.modelo
    print(f"modelo: {modelo}\n")

    ok, detalhe = testar_tool_calling(chave, modelo)
    print(f"  tool calling: {'SIM' if ok else 'NÃO'} — {detalhe}")

    for nome, valor in sorted(limites(chave, modelo).items()):
        print(f"  {nome}: {valor}")

    print()
    if not ok:
        print("NÃO SERVE: o harness da §3 depende de ler_arquivo e buscar.")
        return 1

    print("Serve. Grave o nome no SSM:")
    print("  aws ssm put-parameter --name /pra/llm/modelo \\")
    print(f"    --type String --value {modelo} --overwrite")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
