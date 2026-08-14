"""Entrada do container. FUNÇÃO PURA: pacote entra, achados saem.

Não conhece GitHub, não conhece a regra de decisão, não emite veredito. É a
D14 virando código, e o test_arquitetura.py garante que continue assim.

Uso:
    python -m portcullis.analisador.main /entrada /saida
"""

from __future__ import annotations

import json
import sys
import tempfile
from functools import cache
from pathlib import Path

from portcullis.analisador.pacote import (
    NOME_ACHADOS,
    NOME_CODIGO,
    NOME_CONTEXTO,
    extrair,
    ler_contexto,
)
from portcullis.analisador.semgrep import rodar
from portcullis.modelos import Achado


def _relativizar(caminho: str, raiz: Path) -> str:
    try:
        return str(Path(caminho).resolve().relative_to(raiz.resolve()))
    except ValueError:
        return caminho


def _serializar(achado: Achado, raiz: Path) -> dict:
    return {
        "regra": achado.regra,
        "severidade": achado.severidade.value,
        "categoria": achado.categoria,
        "caminho": _relativizar(achado.caminho, raiz),
        "linha_inicio": achado.linha_inicio,
        "linha_fim": achado.linha_fim,
        "mensagem": achado.mensagem,
    }


def analisar(dir_entrada: Path, dir_saida: Path) -> Path:
    resultado: dict = {
        "ok": False,
        "erro": None,
        "owner": None,
        "repo": None,
        "head_sha": None,
        "hash_regras": "",
        "achados": [],
        "erros_de_analise": [],
    }

    try:
        contexto = ler_contexto(dir_entrada / NOME_CONTEXTO)
        resultado |= {
            "owner": contexto.owner,
            "repo": contexto.repo,
            "head_sha": contexto.head_sha,
        }

        with tempfile.TemporaryDirectory() as temporario:
            raiz = extrair(dir_entrada / NOME_CODIGO, Path(temporario))
            # Sobrescreve o do PR (um `*` zeraria a análise) e anula a lista
            # padrão do semgrep, que pula pastas de teste.
            (raiz / ".semgrepignore").write_text("")

            saida = rodar(raiz)
            resultado |= {
                "ok": True,
                "hash_regras": saida.hash_regras,
                "achados": [_serializar(a, raiz) for a in saida.achados],
                "erros_de_analise": list(saida.erros),
            }
    except Exception as falha:  # noqa: BLE001
        # Blind except de propósito: este é o ponto mais externo do processo.
        # Container que morre calado deixa o PR travado sem mensagem, porque a
        # publicadora só acorda quando o achados.json aparece.
        resultado["erro"] = f"{type(falha).__name__}: {falha}"

    destino = dir_saida / NOME_ACHADOS
    destino.write_text(json.dumps(resultado, indent=2))
    return destino


def principal() -> int:
    if len(sys.argv) != 3:
        print("uso: main.py <dir_entrada> <dir_saida>", file=sys.stderr)
        return 2
    caminho = analisar(Path(sys.argv[1]), Path(sys.argv[2]))
    print(caminho.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())


@cache
def _cliente_s3():
    import boto3

    return boto3.client("s3")


def lambda_handler(evento: dict, _contexto) -> dict:
    """Entrada da Lambda. O invólucro de I/O fica AQUI, nunca em `analisar()`.

    Manter `analisar()` puro é o que deixa o corpus do marco 2 montar um pacote
    na mão e rodar offline, sem AWS e sem GitHub.

    Tudo em /tmp porque o filesystem da imagem é só-leitura em produção — e
    /tmp tem 512 MB fixos, que é de onde vem o teto de extração do pacote.
    """
    bucket = evento["bucket"]
    prefixo = evento["prefixo"]
    s3 = _cliente_s3()

    with tempfile.TemporaryDirectory(dir="/tmp") as temporario:
        raiz = Path(temporario)
        entrada, saida = raiz / "entrada", raiz / "saida"
        entrada.mkdir()
        saida.mkdir()

        for nome in (NOME_CODIGO, NOME_CONTEXTO):
            s3.download_file(Bucket=bucket, Key=f"{prefixo}/{nome}", Filename=str(entrada / nome))

        resultado = analisar(entrada, saida)
        destino = prefixo.replace("entrada/", "saida/", 1)
        s3.upload_file(str(resultado), bucket, f"{destino}/{NOME_ACHADOS}")

    return {"prefixo": destino}
