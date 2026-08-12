"""Invoca o Semgrep como subprocesso e traduz a saída para Achado."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from aduana.modelos import Achado, Severidade

# O Semgrep usa o código de saída para comunicar RESULTADO, não só erro:
# 0 = nada encontrado, 1 = encontrou achados, >=2 = falhou de verdade.
CODIGOS_DE_SUCESSO = (0, 1)

LIMITE_MENSAGEM_ERRO = 300


class SemgrepFalhou(RuntimeError):
    pass


@dataclass(frozen=True)
class SaidaSemgrep:
    achados: tuple[Achado, ...]
    erros: tuple[dict, ...] = ()
    hash_regras: str = ""


def parsear(saida: dict) -> list[Achado]:
    achados: list[Achado] = []
    for resultado in saida.get("results", []):
        extra = resultado["extra"]
        achados.append(
            Achado(
                regra=resultado["check_id"],
                severidade=Severidade(extra["severity"]),
                caminho=resultado["path"],
                linha_inicio=resultado["start"]["line"],
                linha_fim=resultado["end"]["line"],
                mensagem=extra["message"].strip(),
                categoria=extra.get("metadata", {}).get("category"),
            )
        )
    return achados


def erros_de_analise(saida: dict) -> list[dict]:
    """Trechos que o Semgrep não conseguiu interpretar — código não examinado."""
    return [
        {
            "arquivo": erro.get("path"),
            "mensagem": str(erro.get("message", ""))[:LIMITE_MENSAGEM_ERRO],
        }
        for erro in saida.get("errors", [])
    ]


def _executavel() -> str:
    """Prefere o semgrep instalado ao lado deste interpretador: garante que a
    versão que roda é a do mesmo ambiente, não outra qualquer do PATH."""
    vizinho = Path(sys.executable).parent / "semgrep"
    return str(vizinho) if vizinho.exists() else "semgrep"


def _caminhos_de_regras(regras: str | Path | None) -> list[str]:
    bruto = str(regras or os.environ.get("ADUANA_REGRAS", ""))
    caminhos = [parte.strip() for parte in bruto.split(",") if parte.strip()]
    if not caminhos:
        raise SemgrepFalhou("conjunto de regras não definido (ADUANA_REGRAS)")

    faltando = [c for c in caminhos if not Path(c).exists()]
    if faltando:
        raise SemgrepFalhou(f"arquivo de regras ausente: {', '.join(faltando)}")
    return caminhos


def _hash_regras(caminhos: list[str]) -> str:
    """Identifica o conjunto que produziu o veredito. Ver D11."""
    digest = hashlib.sha256()
    for caminho in sorted(caminhos):
        digest.update(Path(caminho).read_bytes())
    return digest.hexdigest()[:12]


def rodar(
    raiz: Path,
    regras: str | Path | None = None,
    timeout_s: int = 600,
) -> SaidaSemgrep:
    caminhos_regras = _caminhos_de_regras(regras)

    comando = [
        _executavel(),
        "scan",
        *(f"--config={caminho}" for caminho in caminhos_regras),
        "--json",
        "--quiet",
        # Telemetria desligada: no container o egress só permite S3.
        "--metrics=off",
        # Sem isto, um `# nosemgrep` escrito no PR desliga o portão.
        "--disable-nosem",
        # Alvo `.` com cwd na raiz: os caminhos saem relativos ao repositório,
        # que é o formato que a anotação do Check Run exige.
        ".",
    ]
    try:
        proc = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=raiz,
            # O código de saída 1 significa "achou algo", não falha.
            check=False,
        )
    except subprocess.TimeoutExpired as erro:
        raise SemgrepFalhou(f"semgrep estourou {timeout_s}s") from erro

    if proc.returncode not in CODIGOS_DE_SUCESSO:
        raise SemgrepFalhou(f"semgrep saiu com {proc.returncode}: {proc.stderr[:500]}")

    dados = json.loads(proc.stdout)
    return SaidaSemgrep(
        achados=tuple(parsear(dados)),
        erros=tuple(erros_de_analise(dados)),
        hash_regras=_hash_regras(caminhos_regras),
    )
