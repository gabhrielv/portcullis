"""Gera corpus/REVISAO.md: os 20 casos num arquivo só, para leitura humana.

Ler 20 casos espalhados em 40 arquivos é o tipo de trabalho que ninguém faz
duas vezes. Este script junta código, gabarito e argumento num lugar só, com os
falso-positivos primeiro — que são os que a D12 diz serem difíceis de escrever
e os únicos que medem alguma coisa se estiverem fracos.

O arquivo gerado NÃO é versionado: ele é derivado do gabarito e das árvores.

Uso:  .venv/bin/python corpus/revisao.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent


def _numerar(texto: str) -> str:
    return "\n".join(f"{n:>3}  {linha}" for n, linha in enumerate(texto.splitlines(), 1))


def _pares(entradas: list[dict]) -> list[str]:
    por_regra: dict[str, list[dict]] = {}
    for entrada in entradas:
        por_regra.setdefault(entrada["alvo"]["regra"].split(".")[-1], []).append(entrada)

    linhas = ["| regra | vulneráveis | falso-positivos |", "|---|---|---|"]
    for regra, casos in sorted(por_regra.items()):
        reais = [c["id"] for c in casos if c["gabarito"] == "VULNERAVEL"]
        falsos = [c["id"] for c in casos if c["gabarito"] == "FALSO_POSITIVO"]
        if reais and falsos:
            linhas.append(f"| `{regra}` | {', '.join(reais)} | {', '.join(falsos)} |")
    return linhas


def _caso(entrada: dict) -> list[str]:
    caso = RAIZ / "casos" / entrada["id"]
    alvo = entrada["alvo"]
    linhas = [
        f"## `{entrada['id']}`",
        "",
        f"**{entrada['dificuldade']}** · padrão: `{entrada['padrao']}`",
        "",
        f"Achado julgado: **`{alvo['arquivo']}:{alvo['linha']}`**  ",
        f"Regra: `{alvo['regra'].split('.')[-1]}`",
        "",
        f"**Meu argumento:** {' '.join(entrada['motivo'].split())}",
        "",
    ]
    for arquivo in sorted(p for p in (caso / "codigo").rglob("*") if p.is_file()):
        relativo = arquivo.relative_to(caso / "codigo").as_posix()
        relativo = relativo.split("/", 1)[1] if "/" in relativo else relativo
        marca = "  ← **o achado está aqui**" if relativo == alvo["arquivo"] else ""
        corpo = arquivo.read_text(errors="replace").rstrip()
        linhas += [f"`{relativo}`{marca}", "", "```python", _numerar(corpo), "```", ""]
    return linhas + ["---", ""]


def gerar() -> Path:
    entradas = yaml.safe_load((RAIZ / "gabarito.yaml").read_text())

    linhas = [
        "# Revisão do corpus — 20 casos",
        "",
        "> Gerado por `corpus/revisao.py`. **Não edite aqui** — a fonte é",
        "> `corpus/gabarito.yaml` e as árvores em `corpus/casos/<id>/codigo/repo/`.",
        "",
        "## O que julgar",
        "",
        "Para cada **falso-positivo**: *eu erraria, lendo só a linha apontada?*",
        "Se não, o caso está fácil demais e mede pouco.",
        "",
        "Para cada **vulnerável**: *dá para acertar sem investigar?*",
        "",
        "---",
        "",
        "## Os pares",
        "",
        "Cinco regras disparam nos dois lados do gabarito. **O id da regra não",
        "carrega sinal** — um agente que decidisse pelo nome tiraria 50%.",
        "",
        *_pares(entradas),
        "",
        "---",
        "",
    ]

    for rotulo, gabarito in (("FALSO-POSITIVOS", "FALSO_POSITIVO"), ("VULNERÁVEIS", "VULNERAVEL")):
        deste = [e for e in entradas if e["gabarito"] == gabarito]
        linhas += [f"# {rotulo} ({len(deste)})", ""]
        for entrada in deste:
            linhas += _caso(entrada)

    destino = RAIZ / "REVISAO.md"
    destino.write_text("\n".join(linhas))
    return destino


if __name__ == "__main__":
    print(gerar())
