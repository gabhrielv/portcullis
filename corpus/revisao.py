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
from congelar import raiz_do_caso

RAIZ = Path(__file__).resolve().parent

# `.gitignore` e `.tfvars` fechados em ```python mentem sobre o que são, e o
# palheiro das variantes de escala traz .cfg, .txt e .json.
CERCA_POR_SUFIXO = {
    ".py": "python",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".cfg": "ini",
    ".ini": "ini",
    ".sh": "bash",
    ".tf": "hcl",
}


def _cerca(caminho: Path) -> str:
    return CERCA_POR_SUFIXO.get(caminho.suffix, "text")


SUFIXO_GRANDE = "-grande"


def _do_caso_pequeno(entrada: dict) -> set[str] | None:
    """Os arquivos da variante pequena correspondente.

    Derivado do caso base, não de uma lista de pastas do palheiro: assim o
    recorte continua certo quando o `palheiro.py` mudar de layout, e não perde
    a cadeia de chamadores só porque o `motivo` não a cita por nome.
    """
    base = RAIZ / "casos" / entrada["id"].removesuffix(SUFIXO_GRANDE)
    raiz = base / "codigo" / "repo"
    if not raiz.is_dir():
        return None
    return {p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file()}


def _evidencia(entrada: dict) -> list[str]:
    """O que conta como raciocínio certo, não só como veredito certo."""
    linhas = ["**Evidência aceita:**", ""]
    for esperada in entrada["evidencia_aceita"]:
        campos = ", ".join(f"`{k}: {v}`" for k, v in esperada.items())
        linhas.append(f"- {campos}")
    return linhas + [""]


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
        f"**{entrada['dificuldade']}** · padrão: `{entrada['padrao']}`"
        + (f"  ·  escala **{entrada['escala']}**" if entrada.get("escala") else "")
        + ("  ·  🪤 **armadilha**" if entrada.get("arma_falso_negativo") else ""),
        "",
        f"Achado julgado: **`{alvo['arquivo']}:{alvo['linha']}`**  ",
        f"Regra: `{alvo['regra'].split('.')[-1]}`",
        "",
        f"**Meu argumento:** {' '.join(entrada['motivo'].split())}",
        "",
        *_evidencia(entrada),
    ]
    raiz = raiz_do_caso(caso)
    arquivos = sorted(p for p in raiz.rglob("*") if p.is_file())

    # 150 arquivos de enchimento num Markdown é o oposto do que este documento
    # existe para fazer. Na escala grande entra só o caminho que decide o caso.
    do_caso = _do_caso_pequeno(entrada) if entrada.get("escala") == "grande" else None
    if do_caso is not None:
        interessantes = [p for p in arquivos if p.relative_to(raiz).as_posix() in do_caso]
        linhas += [
            (
                f"> Escala grande: **{len(arquivos)} arquivos** na árvore, "
                f"{len(arquivos) - len(interessantes)} de enchimento inerte gerado "
                "por `palheiro.py`. Abaixo, só o caminho que decide o caso."
            ),
            "",
        ]
        arquivos = interessantes

    for arquivo in arquivos:
        relativo = arquivo.relative_to(raiz).as_posix()
        marca = "  ← **o achado está aqui**" if relativo == alvo["arquivo"] else ""
        corpo = arquivo.read_text(errors="replace").rstrip()
        linhas += [
            f"`{relativo}`{marca}",
            "",
            f"```{_cerca(arquivo)}",
            _numerar(corpo),
            "```",
            "",
        ]
    return linhas + ["---", ""]


def gerar() -> Path:
    entradas = yaml.safe_load((RAIZ / "gabarito.yaml").read_text())

    linhas = [
        f"# Revisão do corpus — {len(entradas)} casos",
        "",
        "> Gerado por `corpus/revisao.py`. **Não edite aqui** — a fonte é",
        "> `corpus/gabarito.yaml` e as árvores em `corpus/casos/<id>/codigo/repo/`.",
        "",
        "## O que julgar",
        "",
        "Para cada **falso-positivo**: *eu erraria, lendo só a linha apontada?*",
        "Se não, o caso está fácil demais e mede pouco.",
        "",
        "Para cada **vulnerável**: *dá para acertar sem investigar?* E, se dá,",
        "ele está marcado como 🪤 **armadilha**? Só a armadilha consegue arrancar",
        "um falso-negativo — nos outros o portão já bloqueia por padrão, e o",
        "acerto não mede o agente.",
        "",
        "Para **todos**: a *evidência aceita* é mesmo o único raciocínio honesto?",
        "Se houver um segundo caminho defensável que não está na lista, o placar",
        "vai contar raciocínio certo como errado.",
        "",
        "---",
        "",
        "## Os pares",
        "",
        "Quatro regras disparam nos dois lados do gabarito. **O id da regra não",
        "carrega sinal** — um agente que decidisse pelo nome tiraria 50%.",
        "",
        *_pares(entradas),
        "",
        "---",
        "",
    ]

    for rotulo, gabarito in (("FALSO-POSITIVOS", "FALSO_POSITIVO"), ("VULNERÁVEIS", "VULNERAVEL")):
        deste = [e for e in entradas if e["gabarito"] == gabarito]
        deste.sort(key=lambda e: (e.get("escala", "") == "grande", e["id"]))
        linhas += [f"# {rotulo} ({len(deste)})", ""]
        for entrada in deste:
            linhas += _caso(entrada)

    destino = RAIZ / "REVISAO.md"
    destino.write_text("\n".join(linhas))
    return destino


if __name__ == "__main__":
    print(gerar())
