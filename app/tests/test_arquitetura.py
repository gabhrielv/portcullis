"""Garante as restrições G6 e G11 mecanicamente, não por disciplina.

O analisador não fala com o GitHub e não emite veredito (D14). A investigadora
lê código de terceiro e não pode ter credencial do GitHub nem escrever
auditoria (D20) — ela PODE importar a regra, para pré-triar o que investigar.

Promessa que só existe em prosa é promessa que a próxima refatoração quebra.
"""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "portcullis"

PROIBIDOS = {
    "analisador": ("portcullis.github", "portcullis.decisao", "portcullis.persistencia"),
    "investigadora": ("portcullis.github", "portcullis.persistencia"),
    "agente": ("portcullis.github", "portcullis.persistencia", "boto3"),
}


def test_pastas_respeitam_a_separacao_de_privilegio():
    for pasta, proibidos in PROIBIDOS.items():
        for arquivo in (SRC / pasta).rglob("*.py"):
            conteudo = arquivo.read_text()
            for proibido in proibidos:
                assert proibido not in conteudo, (
                    f"{pasta}/{arquivo.name} importa {proibido} — viola a separação"
                )
