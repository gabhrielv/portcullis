"""O corpus é dado, e dado apodrece em silêncio. Isto tranca o apodrecimento."""

import json
from pathlib import Path

import pytest
import yaml

RAIZ_CORPUS = Path(__file__).resolve().parents[2] / "corpus"
GABARITOS_VALIDOS = {"VULNERAVEL", "FALSO_POSITIVO"}
DIFICULDADES_VALIDAS = {"facil", "media", "dificil"}


def entradas():
    return yaml.safe_load((RAIZ_CORPUS / "gabarito.yaml").read_text())


def _casa_alvo(achado: dict, alvo: dict) -> bool:
    """Mesma comparação do `corpus/congelar.py`, repetida de propósito.

    `corpus/` não está no sys.path daqui, e a T1 do marco 1 decidiu que o
    conftest não mexe nele. São três linhas, e o teste conferir o dado por
    conta própria vale mais que o import.
    """
    return (
        achado["caminho"] == alvo["arquivo"]
        and achado["linha_inicio"] <= alvo["linha"] <= achado["linha_fim"]
        and achado["regra"] == alvo["regra"]
    )


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_caso_tem_os_campos_obrigatorios(entrada):
    assert entrada["gabarito"] in GABARITOS_VALIDOS
    assert entrada["dificuldade"] in DIFICULDADES_VALIDAS
    assert entrada["motivo"].strip()
    alvo = entrada["alvo"]
    assert alvo["arquivo"] and alvo["linha"] > 0 and alvo["regra"]


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_caso_esta_congelado_e_o_alvo_existe(entrada):
    caso = RAIZ_CORPUS / "casos" / entrada["id"]
    achados = json.loads((caso / "achados.json").read_text())["achados"]
    alvo = entrada["alvo"]
    assert any(_casa_alvo(a, alvo) for a in achados), (
        f"{entrada['id']}: nada congelado em {alvo['arquivo']}:{alvo['linha']} "
        f"regra={alvo['regra']}"
    )


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_o_alvo_e_um_achado_so(entrada):
    """Alvo ambíguo mede o achado errado sem avisar: a linha 12 do
    `sqli-direto` tem três achados sobrepostos, de severidades diferentes."""
    caso = RAIZ_CORPUS / "casos" / entrada["id"]
    achados = json.loads((caso / "achados.json").read_text())["achados"]
    casaram = [a for a in achados if _casa_alvo(a, entrada["alvo"])]
    assert len(casaram) == 1, f"{entrada['id']}: {len(casaram)} achados casam com o alvo"


def test_ids_sao_unicos():
    ids = [e["id"] for e in entradas()]
    assert len(ids) == len(set(ids))
