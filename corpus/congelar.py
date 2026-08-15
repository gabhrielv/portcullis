"""Transforma cada caso do gabarito num pacote de trabalho e congela os achados.

Roda o MESMO `analisar()` que roda na Lambda, sobre o MESMO formato de pacote
que a buscadora monta. Se o corpus e a produção divergirem, é aqui que aparece.

Uso:  .venv/bin/python corpus/congelar.py [id-do-caso ...]
"""

from __future__ import annotations

import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

from portcullis.analisador.main import analisar
from portcullis.analisador.pacote import (
    NOME_ACHADOS,
    NOME_CODIGO,
    NOME_CONTEXTO,
    escrever_contexto,
)
from portcullis.modelos import Contexto, Evento, FaixaLinhas

RAIZ = Path(__file__).resolve().parent
CASOS = RAIZ / "casos"


class CasoInvalido(RuntimeError):
    pass


def ler_gabarito() -> list[dict]:
    return yaml.safe_load((RAIZ / "gabarito.yaml").read_text())


def _contexto(entrada: dict) -> Contexto:
    return Contexto(
        owner="corpus",
        repo=entrada["id"],
        head_sha="0" * 40,
        evento=Evento.PULL_REQUEST,
        linhas_tocadas={
            arquivo: tuple(FaixaLinhas(i, f) for i, f in faixas)
            for arquivo, faixas in entrada["linhas_tocadas"].items()
        },
        numero_pr=1,
    )


def _empacotar(pasta_codigo: Path, destino: Path) -> None:
    with tarfile.open(destino, "w:gz") as tar:
        for item in sorted(pasta_codigo.iterdir()):
            tar.add(item, arcname=item.name)


def casa_alvo(achado: dict, alvo: dict) -> bool:
    """Casa um achado congelado com o alvo do gabarito.

    A regra entra na comparação porque uma linha acumula achados sobrepostos:
    a 12 do `sqli-direto` tem três, de severidades diferentes. Sem a regra, o
    corpus mediria o que o semgrep listasse primeiro.
    """
    return (
        achado["caminho"] == alvo["arquivo"]
        and achado["linha_inicio"] <= alvo["linha"] <= achado["linha_fim"]
        and achado["regra"] == alvo["regra"]
    )


def _conferir_alvo(entrada: dict, achados: list[dict]) -> None:
    """Caso que não dispara o scanner mede coisa nenhuma.

    Falhar alto aqui é o ponto: um falso-positivo "convincente" que o semgrep
    ignora não é um caso difícil, é um caso ausente — e ele passaria batido no
    placar como se o agente tivesse acertado.
    """
    alvo = entrada["alvo"]
    if not any(casa_alvo(a, alvo) for a in achados):
        encontrados = [
            f"{a['caminho']}:{a['linha_inicio']}-{a['linha_fim']} "
            f"[{a['severidade']}/{a['categoria']}] {a['regra']}"
            for a in achados
        ]
        raise CasoInvalido(
            f"{entrada['id']}: nenhum achado casa com {alvo['arquivo']}:{alvo['linha']} "
            f"regra={alvo['regra']}.\n  Achou: " + ("\n         ".join(encontrados) or "nada")
        )


def congelar(entrada: dict) -> None:
    caso = CASOS / entrada["id"]
    codigo = caso / "codigo"
    if not codigo.is_dir():
        raise CasoInvalido(f"{entrada['id']}: falta a pasta codigo/")

    with tempfile.TemporaryDirectory() as temporario:
        pasta = Path(temporario)
        dir_entrada, dir_saida = pasta / "entrada", pasta / "saida"
        dir_entrada.mkdir()
        dir_saida.mkdir()

        _empacotar(codigo, dir_entrada / NOME_CODIGO)
        escrever_contexto(_contexto(entrada), dir_entrada / NOME_CONTEXTO)

        resultado = json.loads(analisar(dir_entrada, dir_saida).read_text())
        if not resultado["ok"]:
            raise CasoInvalido(f"{entrada['id']}: análise falhou — {resultado['erro']}")

        _conferir_alvo(entrada, resultado["achados"])

        shutil.copy(dir_entrada / NOME_CONTEXTO, caso / NOME_CONTEXTO)
        (caso / NOME_ACHADOS).write_text(json.dumps(resultado, indent=2))

    # `flush` porque cada caso leva ~30 s e a saída não é tty quando isto roda
    # pelo Makefile: sem ele, as 20 linhas só aparecem no fim, todas juntas.
    print(f"{entrada['id']}: {len(resultado['achados'])} achados", flush=True)


def principal(ids: list[str]) -> int:
    entradas = [e for e in ler_gabarito() if not ids or e["id"] in ids]
    if not entradas:
        print("nenhum caso casou", file=sys.stderr)
        return 2
    for entrada in entradas:
        congelar(entrada)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
