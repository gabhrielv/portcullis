"""Roda o corpus e imprime o placar. Ver D12.

O número que importa NÃO é acurácia. Marcar falso-positivo como real custa o seu
tempo; marcar real como falso-positivo deixa vulnerabilidade passar. Por isso o
falso-negativo sai destacado.

A chave sai do SSM, nunca do ambiente — a G2 não abre exceção para bancada
local, e chave em variável de ambiente vaza para `ps`, para o histórico do
shell e para qualquer comando que imprima `env`.

Uso:  .venv/bin/python corpus/rodar.py [id-do-caso ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from congelar import CASOS, casa_alvo, ler_gabarito

from pra.agente.ferramentas import Caixa
from pra.agente.loop import investigar
from pra.config import obrigatoria, parametro_ssm
from pra.decisao.regra import silencia_por_evidencia
from pra.llm.cliente import CotaEsgotada, ProvedorIndisponivel
from pra.llm.groq import ClienteGroq
from pra.modelos import Achado, Severidade

SAIDA = Path(__file__).resolve().parent / "ultimo-placar.json"


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
            )
    raise RuntimeError(f"{caso.name}: alvo não está nos achados congelados")


def _raiz_do_caso(caso: Path) -> Path:
    """A mesma raiz que a extração devolve em produção: `codigo/repo/`."""
    pastas = [p for p in (caso / "codigo").iterdir() if p.is_dir()]
    if len(pastas) != 1:
        raise RuntimeError(f"{caso.name}: esperava uma pasta raiz em codigo/")
    return pastas[0]


def rodar(entradas: list[dict], cliente) -> tuple[list[dict], str | None]:
    """Devolve as linhas medidas e, se a cota acabou no meio, o motivo.

    Parar e devolver o que já mediu não é gentileza: cada caso custa cota, e
    perder 13 medições porque a 14ª estourou obrigaria a pagar tudo de novo.
    """
    linhas: list[dict] = []
    for entrada in entradas:
        caso = CASOS / entrada["id"]
        achado = _achado_do_alvo(caso, entrada["alvo"])
        try:
            evidencia = investigar(achado, Caixa(_raiz_do_caso(caso)), cliente)
        except (CotaEsgotada, ProvedorIndisponivel) as falha:
            return linhas, f"{type(falha).__name__}: {falha}"

        silenciou = silencia_por_evidencia(evidencia)
        esperado_silenciar = entrada["gabarito"] == "FALSO_POSITIVO"
        linhas.append(
            {
                "id": entrada["id"],
                "dificuldade": entrada["dificuldade"],
                "gabarito": entrada["gabarito"],
                "silenciou": silenciou,
                "acertou": silenciou == esperado_silenciar,
                "falso_negativo": silenciou and not esperado_silenciar,
                "passos": evidencia.passos,
                "tokens": evidencia.tokens,
                "raciocinio": evidencia.raciocinio,
            }
        )
        marca = "ok " if linhas[-1]["acertou"] else "ERRO"
        print(f"{marca} {entrada['id']:<34} {evidencia.passos} passos", flush=True)
    return linhas, None


def placar(linhas: list[dict]) -> str:
    reais = [x for x in linhas if x["gabarito"] == "VULNERAVEL"]
    positivos = [x for x in linhas if x["gabarito"] == "FALSO_POSITIVO"]
    pegos = [x for x in reais if not x["silenciou"]]
    silenciados_certos = [x for x in positivos if x["silenciou"]]
    falso_negativos = [x for x in linhas if x["falso_negativo"]]

    saida = [
        "",
        f"recall             {len(pegos)}/{len(reais)}",
        f"falso-negativos    {len(falso_negativos)}/{len(reais)}   <- o que importa",
        f"ruído removido     {len(silenciados_certos)}/{len(positivos)}",
        f"acertos            {sum(x['acertou'] for x in linhas)}/{len(linhas)}",
        f"passos (média)     {sum(x['passos'] for x in linhas) / max(len(linhas), 1):.1f}",
        f"tokens (total)     {sum(x['tokens'] for x in linhas)}",
        "",
    ]
    for dificuldade in ("facil", "media", "dificil"):
        deste = [x for x in linhas if x["dificuldade"] == dificuldade]
        if deste:
            saida.append(
                f"  {dificuldade:<8} {sum(x['acertou'] for x in deste)}/{len(deste)}"
            )
    if falso_negativos:
        saida += ["", "FALSO-NEGATIVOS:"]
        saida += [f"  {x['id']}: {x['raciocinio'][:100]}" for x in falso_negativos]
    return "\n".join(saida)


def principal(ids: list[str]) -> int:
    entradas = [e for e in ler_gabarito() if not ids or e["id"] in ids]
    if not entradas:
        print("nenhum caso casou", file=sys.stderr)
        return 2

    cliente = ClienteGroq(
        parametro_ssm(obrigatoria("PRA_PARAM_CHAVE_LLM")),
        parametro_ssm(obrigatoria("PRA_PARAM_MODELO_LLM")),
    )
    linhas, interrompido = rodar(entradas, cliente)

    if linhas:
        print(placar(linhas))
        SAIDA.write_text(json.dumps(linhas, indent=2))

    if interrompido:
        print(
            f"\nINTERROMPIDO em {len(linhas)}/{len(entradas)} casos: {interrompido}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
