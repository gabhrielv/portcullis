import json
import subprocess
from pathlib import Path

import pytest

from portcullis.analisador.semgrep import (
    SemgrepFalhou,
    erros_de_analise,
    parsear,
    rodar,
)
from portcullis.modelos import Severidade

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
    monkeypatch.delenv("PORTCULLIS_REGRAS", raising=False)
    with pytest.raises(SemgrepFalhou):
        rodar(tmp_path)


def _capturar(monkeypatch) -> dict:
    capturado: dict = {}

    def falso_run(comando, **kw):
        capturado["comando"] = comando
        capturado["cwd"] = kw.get("cwd")
        return subprocess.CompletedProcess(comando, 0, stdout='{"results":[],"errors":[]}', stderr="")

    monkeypatch.setattr(subprocess, "run", falso_run)
    return capturado


def test_rodar_pede_supressao_inline_desligada(tmp_path, monkeypatch):
    # Sem --disable-nosem, um `# nosemgrep` escrito no PR desliga o portão.
    regras = tmp_path / "regras.yaml"
    regras.write_text("rules: []\n")
    capturado = _capturar(monkeypatch)

    rodar(tmp_path, regras=regras)

    assert "--disable-nosem" in capturado["comando"]
    assert "--metrics=off" in capturado["comando"]
    assert f"--config={regras}" in capturado["comando"]


def test_rodar_escaneia_a_raiz_por_caminho_relativo(tmp_path, monkeypatch):
    # Alvo absoluto faz o semgrep devolver caminho absoluto, e a anotação do
    # Check Run precisa do caminho relativo ao repositório.
    regras = tmp_path / "regras.yaml"
    regras.write_text("rules: []\n")
    capturado = _capturar(monkeypatch)

    rodar(tmp_path, regras=regras)

    assert capturado["comando"][-1] == "."
    assert capturado["cwd"] == tmp_path


@pytest.mark.integracao
def test_rodar_encontra_achados_reais_no_hoppr(tmp_path):
    import os

    from conftest import CAMINHO_HOPPR

    regras = os.environ.get("PORTCULLIS_REGRAS", "")
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


def _regras_falsas(tmp_path):
    a = tmp_path / "default.yaml"
    b = tmp_path / "audit.yaml"
    a.write_text("rules: []\n")
    b.write_text("rules: [x]\n")
    return a, b


def test_rodar_aceita_varios_conjuntos_de_regras(tmp_path, monkeypatch):
    a, b = _regras_falsas(tmp_path)
    capturado = {}

    def falso_run(comando, **kw):
        capturado["comando"] = comando
        return subprocess.CompletedProcess(comando, 0, stdout='{"results":[],"errors":[]}', stderr="")

    monkeypatch.setattr(subprocess, "run", falso_run)
    rodar(tmp_path, regras=f"{a},{b}")

    assert f"--config={a}" in capturado["comando"]
    assert f"--config={b}" in capturado["comando"]


def test_hash_das_regras_identifica_o_conjunto(tmp_path, monkeypatch):
    a, b = _regras_falsas(tmp_path)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda comando, **kw: subprocess.CompletedProcess(
            comando, 0, stdout='{"results":[],"errors":[]}', stderr=""
        ),
    )

    primeiro = rodar(tmp_path, regras=f"{a},{b}").hash_regras
    assert len(primeiro) == 12
    assert rodar(tmp_path, regras=f"{a},{b}").hash_regras == primeiro

    b.write_text("rules: [x, y]\n")
    assert rodar(tmp_path, regras=f"{a},{b}").hash_regras != primeiro


def test_arquivo_de_regras_ausente_falha_alto(tmp_path):
    with pytest.raises(SemgrepFalhou, match="ausente"):
        rodar(tmp_path, regras=str(tmp_path / "nao-existe.yaml"))


def test_prefixo_vem_das_pastas_do_arquivo_de_regras():
    from portcullis.analisador.semgrep import prefixo_de_regra

    raiz = Path("/tmp/tmpabc/gabhrielv-hoppr-a1b2c3")
    assert prefixo_de_regra("/opt/portcullis/regras/default.yaml", raiz) == "opt.portcullis.regras."
    assert prefixo_de_regra(str(raiz.parent / "regras.yaml"), raiz) == ""


def test_id_da_regra_nao_carrega_o_caminho_do_arquivo_de_regras():
    # Sem isso o mesmo achado teria id diferente na maquina e no container,
    # e a lista de excecoes nunca casaria.
    saida = {
        "results": [
            {
                "check_id": "opt.portcullis.regras.python.jwt.security.jwt-hardcode",
                "path": "a.py",
                "start": {"line": 1},
                "end": {"line": 1},
                "extra": {"severity": "ERROR", "message": "m", "metadata": {}},
            }
        ]
    }
    achado = parsear(saida, ("opt.portcullis.regras.",))[0]
    assert achado.regra == "python.jwt.security.jwt-hardcode"


def _saida_com_cwe(cwe):
    return {
        "results": [
            {
                "check_id": "r",
                "path": "a.py",
                "start": {"line": 1},
                "end": {"line": 1},
                "extra": {
                    "severity": "ERROR",
                    "message": "m",
                    "metadata": {"category": "security", "cwe": cwe},
                },
            }
        ],
        "errors": [],
    }


def test_parsear_extrai_os_cwe_da_regra():
    """O CWE é o que separa achado de fluxo de dados de achado que não é — e
    é ele que decide se o agente chega a ver o achado (D6)."""
    cwe = ["CWE-89: Improper Neutralization of Special Elements used in an SQL Command"]
    assert parsear(_saida_com_cwe(cwe))[0].cwes == ("89",)


def test_parsear_aceita_cwe_declarado_como_texto_solto():
    assert parsear(_saida_com_cwe("CWE-79: Cross-site Scripting"))[0].cwes == ("79",)


def test_parsear_junta_varios_cwe_da_mesma_regra():
    cwe = ["CWE-94: Code Injection", "CWE-95: Eval Injection"]
    assert parsear(_saida_com_cwe(cwe))[0].cwes == ("94", "95")


def test_parsear_sem_cwe_devolve_tupla_vazia():
    """Vazio bloqueia: regra sem CWE nunca vira achado investigável."""
    assert parsear(carregar_fixture())[2].cwes == ()
