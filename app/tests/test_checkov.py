"""O parser do Checkov. Os dados vêm de uma execução real de 20/08/2026,
com a 3.3.13 sobre a Terraform deste projeto — não de formato inventado."""

import json

import pytest

from pra.analisador.checkov import (
    PREFIXO_SKIP,
    CheckovFalhou,
    parsear,
    rodar,
    tem_terraform,
    versao_do_conjunto,
)
from pra.decisao.regra import investigavel
from pra.modelos import Severidade

SAIDA_REAL = {
    "check_type": "terraform",
    "summary": {"passed": 166, "failed": 66, "checkov_version": "3.3.13"},
    "results": {
        "failed_checks": [
            {
                "check_id": "CKV_AWS_26",
                "check_name": "Ensure all data stored in the SNS topic is encrypted",
                "file_path": "/modules/alertas/main.tf",
                "file_line_range": [3, 5],
                "resource": "module.alertas.aws_sns_topic.alertas",
                "severity": None,
            }
        ]
    },
}


def test_parseia_um_achado_real():
    achado = parsear(SAIDA_REAL)[0]
    assert achado.regra == "CKV_AWS_26"
    assert achado.linha_inicio == 3 and achado.linha_fim == 5
    assert "SNS" in achado.mensagem


def test_a_barra_inicial_do_caminho_sai():
    """`file_path` vem como `/modules/...`. Com a barra, o caminho nunca
    casaria com `linhas_tocadas` — nenhum achado seria novo e o portão
    ficaria mudo em vez de bloquear."""
    assert parsear(SAIDA_REAL)[0].caminho == "modules/alertas/main.tf"


def test_todo_achado_entra_como_erro():
    """O nível gratuito não classifica severidade: `severity` vem `None`.
    Inventar um eixo que a ferramenta não dá seria palpite; ERRO bloqueia,
    e a discordância legítima vive no `excecoes.py` com o motivo escrito."""
    assert parsear(SAIDA_REAL)[0].severidade is Severidade.ERRO


def test_achado_de_iac_nunca_chega_ao_agente():
    """A D26 restringe o agente a fluxo de dados. "De onde vem o valor" não
    quer dizer nada num tópico sem criptografia — e responder `nao` ali
    silenciaria. Sem CWE e fora de REGRAS_DE_FLUXO, a regra já recusa."""
    assert not investigavel(parsear(SAIDA_REAL)[0])


def test_aceita_lista_de_frameworks():
    """O Checkov devolve lista quando roda mais de um framework no alvo."""
    assert len(parsear([SAIDA_REAL, SAIDA_REAL])) == 2


def test_achado_sem_faixa_de_linha_e_descartado():
    """Sem linha não há como decidir se é novo, e anotação sem linha não
    existe no Check Run."""
    ruim = {"results": {"failed_checks": [{"check_id": "X", "file_path": "/a.tf"}]}}
    assert parsear(ruim) == []


def test_a_versao_entra_na_impressao_digital():
    assert versao_do_conjunto(SAIDA_REAL) == "3.3.13"


def test_versao_ausente_nao_explode():
    assert versao_do_conjunto({"summary": {}}) == ""


def test_so_roda_onde_ha_terraform(tmp_path):
    """Sem isto, todo repositório Python pagaria o tempo do Checkov para
    ele não achar arquivo nenhum."""
    (tmp_path / "app.py").write_text("x = 1\n")
    assert not tem_terraform(tmp_path)

    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "main.tf").write_text('resource "aws_s3_bucket" "b" {}\n')
    assert tem_terraform(tmp_path)


def test_checkov_ausente_vira_falha_nomeada(tmp_path, monkeypatch):
    """A imagem pode subir sem ele. O erro precisa dizer isso, e não um
    FileNotFoundError cru que ninguém liga ao scanner."""
    def sem_binario(*_a, **_k):
        raise FileNotFoundError("checkov")

    monkeypatch.setattr("pra.analisador.checkov.subprocess.run", sem_binario)
    with pytest.raises(CheckovFalhou, match="não está instalado"):
        rodar(tmp_path)


def test_saida_que_nao_e_json_vira_falha_nomeada(tmp_path, monkeypatch):
    class Proc:
        returncode = 0
        stdout = "nao e json"
        stderr = ""

    monkeypatch.setattr("pra.analisador.checkov.subprocess.run", lambda *a, **k: Proc())
    with pytest.raises(CheckovFalhou, match="JSON"):
        rodar(tmp_path)


def test_codigo_1_significa_achou_algo_nao_falhou(tmp_path, monkeypatch):
    class Proc:
        returncode = 1
        stdout = json.dumps(SAIDA_REAL)
        stderr = ""

    monkeypatch.setattr("pra.analisador.checkov.subprocess.run", lambda *a, **k: Proc())
    assert len(rodar(tmp_path).achados) == 1


def test_skip_escrito_no_pr_nao_desliga_a_checagem():
    """Medido em 20/08/2026: `#checkov:skip=CKV_AWS_26` no arquivo tira a
    checagem do resultado. É o buraco que o `--disable-nosem` fecha no
    semgrep, e o Checkov não tem flag equivalente — então fecha aqui.

    Quem abre PR no alvo escreve esse comentário. A válvula legítima é o
    `excecoes.py`, que ele não alcança. Sem isto, o portão se desliga a
    pedido de quem ele vigia.
    """
    saida = {
        "results": {
            "failed_checks": [],
            "skipped_checks": [
                {
                    "check_id": "CKV_AWS_26",
                    "check_name": "Ensure all data stored in the SNS topic is encrypted",
                    "file_path": "/infra/main.tf",
                    "file_line_range": [1, 3],
                }
            ],
        }
    }
    achados = parsear(saida)
    assert len(achados) == 1
    assert achados[0].regra == "CKV_AWS_26"
    assert achados[0].severidade is Severidade.ERRO


def test_a_tentativa_de_skip_fica_visivel_no_texto():
    """Quem lê o painel merece saber que alguém tentou desligar."""
    saida = {
        "results": {
            "skipped_checks": [
                {
                    "check_id": "CKV_AWS_26",
                    "check_name": "SNS sem criptografia",
                    "file_path": "/infra/main.tf",
                    "file_line_range": [1, 3],
                }
            ]
        }
    }
    assert parsear(saida)[0].mensagem.startswith(PREFIXO_SKIP)
