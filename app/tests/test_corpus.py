"""O corpus é dado, e dado apodrece em silêncio. Isto tranca o apodrecimento."""

import json
from pathlib import Path

import pytest
import yaml

from pra.decisao.regra import investigavel, silencia_por_evidencia
from pra.modelos import Achado, Evidencia, Resposta, Severidade

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


# ---------------------------------------------------------------------------
# Invariantes que o corpus precisa manter para medir o que diz medir.
# ---------------------------------------------------------------------------

RESPOSTAS_VALIDAS = {"sim", "nao", "nao_sei"}
CAMPOS_DE_EVIDENCIA = {"entrada_controlavel", "sanitizacao_encontrada", "prova_em"}


def _alvo_congelado(entrada: dict) -> dict:
    caso = RAIZ_CORPUS / "casos" / entrada["id"]
    achados = json.loads((caso / "achados.json").read_text())["achados"]
    return next(a for a in achados if _casa_alvo(a, entrada["alvo"]))


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_todo_alvo_e_de_fluxo_de_dados(entrada):
    """As duas perguntas do agente só se aplicam a achado de fluxo. Caso fora
    disso nunca chegaria ao agente em produção — `investigavel()` o barra — e
    o placar o pontuaria como se tivesse chegado."""
    achado = Achado(
        regra=entrada["alvo"]["regra"],
        severidade=Severidade.ERRO,
        caminho=entrada["alvo"]["arquivo"],
        linha_inicio=entrada["alvo"]["linha"],
        linha_fim=entrada["alvo"]["linha"],
        mensagem="",
        cwes=tuple(_alvo_congelado(entrada).get("cwes") or ()),
    )
    assert investigavel(achado), f"{entrada['id']}: CWE {achado.cwes} não é de fluxo"


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_o_alvo_esta_dentro_das_linhas_tocadas(entrada):
    """Se a faixa deriva, `_e_novo` devolve False, o achado vira pré-existente
    e o agente nunca é chamado em produção — enquanto o `rodar.py` continua
    pontuando o caso. Divergência silenciosa entre corpus e produção."""
    achado = _alvo_congelado(entrada)
    faixas = entrada["linhas_tocadas"].get(entrada["alvo"]["arquivo"], [])
    assert any(
        inicio <= achado["linha_fim"] and fim >= achado["linha_inicio"]
        for inicio, fim in faixas
    ), f"{entrada['id']}: nenhuma faixa tocada cruza o alvo"


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_evidencia_aceita_usa_o_vocabulario_do_agente(entrada):
    aceitas = entrada["evidencia_aceita"]
    assert aceitas, f"{entrada['id']}: sem evidência esperada, 'acertou' é só um bit"
    for esperada in aceitas:
        assert set(esperada) <= CAMPOS_DE_EVIDENCIA, f"{entrada['id']}: campo estranho"
        for campo in ("entrada_controlavel", "sanitizacao_encontrada"):
            if campo in esperada:
                assert esperada[campo] in RESPOSTAS_VALIDAS


@pytest.mark.parametrize("entrada", entradas(), ids=lambda e: e["id"])
def test_evidencia_aceita_concorda_com_o_gabarito(entrada):
    """Evidência esperada que silencia num caso VULNERAVEL seria um gabarito
    contra si mesmo: o corpus exigiria o raciocínio que produz o falso-negativo."""
    for esperada in entrada["evidencia_aceita"]:
        silencia = silencia_por_evidencia(
            Evidencia(
                chave="",
                entrada_controlavel=Resposta(esperada.get("entrada_controlavel", "nao_sei")),
                sanitizacao_encontrada=Resposta(
                    esperada.get("sanitizacao_encontrada", "nao_sei")
                ),
                prova_valida="prova_em" in esperada,
            )
        )
        assert silencia is (entrada["gabarito"] == "FALSO_POSITIVO"), (
            f"{entrada['id']}: {esperada} não produz o veredito do gabarito"
        )


def test_so_caso_vulneravel_e_marcado_como_armadilha():
    """Armadilha é o caso capaz de arrancar um falso-negativo. Falso-positivo
    não tem como: o pior que acontece nele é bloquear, que é o padrão."""
    for entrada in entradas():
        if entrada.get("arma_falso_negativo"):
            assert entrada["gabarito"] == "VULNERAVEL", entrada["id"]


def test_o_corpus_tem_armadilha_suficiente_para_o_aceite():
    """O aceite é `falso-negativos == 0` nas armadilhas. Sem armadilha, essa
    métrica é 0/0 e um agente que responde nao_sei em tudo passa."""
    armadilhas = [e for e in entradas() if e.get("arma_falso_negativo")]
    assert len(armadilhas) >= 4
