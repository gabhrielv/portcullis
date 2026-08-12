"""Garante a restrição G6 mecanicamente, não por disciplina.

O container não fala com o GitHub e não emite veredito (D14). Se alguém
acrescentar um desses imports, este teste quebra.
"""

from pathlib import Path

PROIBIDOS = ("aduana.github", "aduana.decisao", "aduana.persistencia")
PASTA_ANALISADOR = Path(__file__).resolve().parents[1] / "src" / "aduana" / "analisador"


def test_analisador_nao_importa_github_nem_decisao():
    for arquivo in PASTA_ANALISADOR.rglob("*.py"):
        conteudo = arquivo.read_text()
        for proibido in PROIBIDOS:
            assert proibido not in conteudo, (
                f"{arquivo.name} importa {proibido} — viola a separação da D14"
            )
