import json
import subprocess
from pathlib import Path

import pytest

from aduana.analisador.semgrep import (
    SemgrepFalhou,
    erros_de_analise,
    parsear,
    rodar,
)
from aduana.modelos import Severidade

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture():
    return json.loads((FIXTURES / "semgrep_saida.json").read_text())


def test_parsear_extrai_todos_os_achados():
    assert len(parsear(carregar_fixture())) == 3


def test_parsear_mapeia_severidade_do_semgrep():
    achados = parsear(carregar_fixture())
    assert achados[0].severidade is Severidade.ERRO
    assert achados[1].severidade is Severidade.AVISO


def test_parsear_preserva_caminho_relativo_e_faixa_de_linhas():
    a = parsear(carregar_fixture())[1]
    assert a.caminho == "backend/app/main.py"
    assert a.linha_inicio == 12
    assert a.linha_fim == 14


def test_parsear_limpa_espaco_da_mensagem():
    assert parsear(carregar_fixture())[0].mensagem == "Detected possible formatted SQL query."


def test_parsear_extrai_a_categoria_da_regra():
    achados = parsear(carregar_fixture())
    assert achados[0].categoria == "security"
    assert achados[1].categoria == "performance"


def test_parsear_sem_categoria_declarada_devolve_none():
    assert parsear(carregar_fixture())[2].categoria is None


def test_parsear_saida_vazia_devolve_lista_vazia():
    assert parsear({"results": [], "errors": []}) == []


def test_parsear_severidade_desconhecida_estoura():
    saida = {
        "results": [
            {
                "check_id": "x",
                "path": "a.py",
                "start": {"line": 1},
                "end": {"line": 1},
                "extra": {"severity": "CATASTROPHIC", "message": "m"},
            }
        ]
    }
    with pytest.raises(ValueError):
        parsear(saida)


def test_erros_de_analise_registram_o_arquivo_nao_lido():
    erros = erros_de_analise(carregar_fixture())
    assert len(erros) == 1
    assert erros[0]["arquivo"] == "frontend/components/events/event-qa.tsx"
    assert "Respostas" in erros[0]["mensagem"]


def test_sem_erros_de_analise_devolve_lista_vazia():
    assert erros_de_analise({"results": [], "errors": []}) == []


def test_rodar_sem_conjunto_de_regras_falha_alto(tmp_path, monkeypatch):
    monkeypatch.delenv("ADUANA_REGRAS", raising=False)
    with pytest.raises(SemgrepFalhou):
        rodar(tmp_path)


def test_rodar_pede_supressao_inline_desligada(tmp_path, monkeypatch):
    # Sem --disable-nosem, um `# nosemgrep` escrito no PR desliga o portão.
    capturado = {}

    def falso_run(comando, **kw):
        capturado["comando"] = comando
        capturado["cwd"] = kw.get("cwd")
        return subprocess.CompletedProcess(comando, 0, stdout='{"results":[],"errors":[]}', stderr="")

    monkeypatch.setattr(subprocess, "run", falso_run)
    rodar(tmp_path, regras="/tmp/regras.yaml")

    assert "--disable-nosem" in capturado["comando"]
    assert "--metrics=off" in capturado["comando"]
    assert "--config=/tmp/regras.yaml" in capturado["comando"]


def test_rodar_escaneia_a_raiz_por_caminho_relativo(tmp_path, monkeypatch):
    # Alvo absoluto faz o semgrep devolver caminho absoluto, e a anotação do
    # Check Run precisa do caminho relativo ao repositório.
    capturado = {}

    def falso_run(comando, **kw):
        capturado["comando"] = comando
        capturado["cwd"] = kw.get("cwd")
        return subprocess.CompletedProcess(comando, 0, stdout='{"results":[],"errors":[]}', stderr="")

    monkeypatch.setattr(subprocess, "run", falso_run)
    rodar(tmp_path, regras="/tmp/regras.yaml")

    assert capturado["comando"][-1] == "."
    assert capturado["cwd"] == tmp_path


@pytest.mark.integracao
def test_rodar_encontra_achados_reais_no_hoppr(tmp_path):
    import os

    from conftest import CAMINHO_HOPPR

    regras = os.environ.get("ADUANA_REGRAS", "")
    if not CAMINHO_HOPPR.exists() or not regras:
        pytest.skip("hoppr ou conjunto de regras ausente")

    # Cópia da árvore versionada: é o mesmo conteúdo do tarball do GitHub, e
    # não suja o repositório alvo.
    arvore = tmp_path / "arvore"
    arvore.mkdir()
    subprocess.run(
        f"git -C {CAMINHO_HOPPR} archive HEAD | tar -x -C {arvore}",
        shell=True,
        check=True,
    )
    (arvore / ".semgrepignore").write_text("")

    saida = rodar(arvore, regras=regras)

    assert saida.achados
    for a in saida.achados:
        assert a.linha_inicio >= 1
        assert not a.caminho.startswith("/")
