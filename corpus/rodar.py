"""Roda o corpus e imprime o placar. Ver D12.

O número que importa NÃO é acurácia, e não é o veredito sozinho. Num portão
fail-closed, um agente que responde `nao_sei` em tudo tira recall perfeito e
zero falso-negativo sem investigar nada — por isso o placar sai com a coluna da
**linha de base** ao lado da medida, e com **raciocínio** separado de veredito.
A aritmética toda vive em `placar.py`, que tem teste; aqui fica a I/O e a cota.

**Repetição seletiva.** `temperature: 0` deixa a amostragem gulosa, não deixa o
provedor determinístico: inferência em lote e roteamento de especialista
dependem da composição do batch. Uma amostra de 1 não distingue mexida boa de
sorte. Os casos que podem mudar de valor — falso-positivos e armadilhas —
rodam N vezes; o resto roda 1, porque neles bloquear é o padrão do portão.

**O placar não sobrescreve.** Cada execução vira um arquivo em `placares/`
nomeado pela versão do prompt e pelo modelo, que é a mesma disciplina que o
`ClienteLLM` já impõe à evidência: sem isso, "mexi no prompt e melhorou" é
memória, não diff.

A chave sai do SSM, nunca do ambiente — a G2 não abre exceção para bancada
local, e chave em variável de ambiente vaza para `ps`, para o histórico do
shell e para qualquer comando que imprima `env`.

Uso:  .venv/bin/python corpus/rodar.py [--repeticoes N] [id-do-caso ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from congelar import CASOS, casa_alvo, ler_gabarito, raiz_do_caso
from placar import aceite, evidencia_bate, mede, render, resumir

from pra.agente.ferramentas import Caixa
from pra.agente.loop import investigar
from pra.agente.prompt import VERSAO_PROMPT
from pra.config import obrigatoria, parametro_ssm
from pra.decisao.regra import silencia_por_evidencia
from pra.llm.cliente import CotaEsgotada, ProvedorIndisponivel
from pra.llm.groq import ClienteGroq
from pra.modelos import Achado, Severidade

PLACARES = Path(__file__).resolve().parent / "placares"


def _achado_do_alvo(caso: Path, alvo: dict) -> Achado:
    """Usa o mesmo `casa_alvo` do congelar: a regra entra na comparação.

    Sem ela, uma linha com achados sobrepostos faria o placar medir um achado
    diferente do que o gabarito julga — e o resultado pareceria legítimo.
    """
    achados = json.loads((caso / "achados.json").read_text())["achados"]
    for dados in achados:
        if casa_alvo(dados, alvo):
            return Achado(
                regra=dados["regra"],
                severidade=Severidade(dados["severidade"]),
                caminho=dados["caminho"],
                linha_inicio=dados["linha_inicio"],
                linha_fim=dados["linha_fim"],
                mensagem=dados["mensagem"],
                categoria=dados.get("categoria"),
                cwes=tuple(dados.get("cwes") or ()),
            )
    raise RuntimeError(f"{caso.name}: alvo não está nos achados congelados")


def _uma_execucao(entrada: dict, achado: Achado, caixa: Caixa, cliente) -> dict:
    evidencia = investigar(achado, caixa, cliente)
    return {
        "silenciou": silencia_por_evidencia(evidencia),
        "raciocinio_bateu": evidencia_bate(evidencia, entrada["evidencia_aceita"]),
        "passos": evidencia.passos,
        "tokens": evidencia.tokens,
        "raciocinio": evidencia.raciocinio,
        "entrada_controlavel": evidencia.entrada_controlavel.value,
        "sanitizacao_encontrada": evidencia.sanitizacao_encontrada.value,
        "prova": evidencia.prova,
        "prova_valida": evidencia.prova_valida,
    }


def rodar(entradas: list[dict], cliente, repeticoes: int) -> tuple[list[dict], str | None]:
    """Devolve as linhas medidas e, se a cota acabou no meio, o motivo.

    Parar e devolver o que já mediu não é gentileza: cada caso custa cota, e
    perder 13 medições porque a 14ª estourou obrigaria a pagar tudo de novo.
    """
    linhas: list[dict] = []
    for entrada in entradas:
        caso = CASOS / entrada["id"]
        achado = _achado_do_alvo(caso, entrada["alvo"])
        caixa = Caixa(raiz_do_caso(caso))
        vezes = repeticoes if mede(entrada) else 1

        execucoes: list[dict] = []
        for _ in range(vezes):
            try:
                execucoes.append(_uma_execucao(entrada, achado, caixa, cliente))
            except (CotaEsgotada, ProvedorIndisponivel) as falha:
                return linhas, f"{type(falha).__name__}: {falha}"

        linha = resumir(entrada, execucoes)
        linhas.append(linha)
        marca = "ok  " if linha["veredito_certo"] else "ERRO"
        razao = "" if linha["raciocinio_certo"] else "  (raciocínio não bateu)"
        oscilou = "" if linha["estavel"] else "  (oscilou)"
        print(
            f"{marca} {entrada['id']:<40} {vezes}x {linha['passos']:.0f} passos{razao}{oscilou}",
            flush=True,
        )
    return linhas, None


def _gravar(linhas: list[dict], modelo: str) -> Path:
    PLACARES.mkdir(exist_ok=True)
    destino = PLACARES / f"{VERSAO_PROMPT}-{modelo}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    destino.write_text(
        json.dumps(
            {"versao_prompt": VERSAO_PROMPT, "modelo": modelo, "linhas": linhas}, indent=2
        )
    )
    return destino


def principal(argumentos: list[str]) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("ids", nargs="*", help="limita aos casos nomeados")
    analisador.add_argument(
        "--repeticoes",
        type=int,
        default=1,
        help="execuções por caso que mede (falso-positivo e armadilha). O aceite roda 3",
    )
    opcoes = analisador.parse_args(argumentos)

    entradas = [e for e in ler_gabarito() if not opcoes.ids or e["id"] in opcoes.ids]
    if not entradas:
        print("nenhum caso casou", file=sys.stderr)
        return 2

    cliente = ClienteGroq(
        parametro_ssm(obrigatoria("PRA_PARAM_CHAVE_LLM")),
        parametro_ssm(obrigatoria("PRA_PARAM_MODELO_LLM")),
    )
    linhas, interrompido = rodar(entradas, cliente, max(1, opcoes.repeticoes))

    if linhas:
        print(render(linhas, entradas))
        print(f"gravado em {_gravar(linhas, cliente.modelo)}")

    if interrompido:
        print(
            f"\nINTERROMPIDO em {len(linhas)}/{len(entradas)} casos: {interrompido}",
            file=sys.stderr,
        )
        return 1

    # Sair com 0 reprovando faria o aceite depender de alguém somar as colunas
    # a olho. Códigos distintos porque as três falhas pedem coisas diferentes:
    # 1 é esperar a cota voltar, 2 é erro de invocação, 3 é o agente regrediu.
    passou, _ = aceite(linhas, entradas)
    if not passou:
        if opcoes.repeticoes < 3:
            print(
                f"\n(rodou com {opcoes.repeticoes} execução(ões); o aceite oficial usa 3)",
                file=sys.stderr,
            )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
