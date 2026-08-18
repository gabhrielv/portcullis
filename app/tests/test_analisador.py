import json
from pathlib import Path

from test_pacote import montar_tar

from pra.analisador import main as analisador
from pra.analisador.pacote import NOME_CONTEXTO, escrever_contexto
from pra.analisador.semgrep import SaidaSemgrep, SemgrepFalhou
from pra.modelos import Achado, Contexto, Evento, FaixaLinhas, Severidade


def montar_pacote(tmp_path: Path) -> Path:
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    montar_tar(entrada, {"gabhrielv-hoppr-a1b2c3/app.py": "x = 1\n"})
    escrever_contexto(
        Contexto(
            owner="gabhrielv",
            repo="hoppr",
            head_sha="a1b2c3",
            evento=Evento.PULL_REQUEST,
            linhas_tocadas={"app.py": (FaixaLinhas(1, 1),)},
            numero_pr=7,
        ),
        entrada / NOME_CONTEXTO,
    )
    return entrada


def preparar(tmp_path, monkeypatch, falso_rodar):
    monkeypatch.setattr(analisador, "rodar", falso_rodar)
    entrada = montar_pacote(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()
    return entrada, saida


def executar(tmp_path, monkeypatch, falso_rodar) -> dict:
    entrada, saida = preparar(tmp_path, monkeypatch, falso_rodar)
    return json.loads(analisador.analisar(entrada, saida).read_text())


def test_analisar_escreve_achados_json(tmp_path, monkeypatch):
    achado = Achado("r1", Severidade.ERRO, "app.py", 1, 1, "achei", categoria="security")
    dados = executar(
        tmp_path,
        monkeypatch,
        lambda raiz, **kw: SaidaSemgrep(achados=(achado,), hash_regras="fd16c10bc6b5"),
    )

    assert dados["ok"] is True
    assert dados["head_sha"] == "a1b2c3"
    assert len(dados["achados"]) == 1
    assert dados["achados"][0]["severidade"] == "ERROR"
    assert dados["achados"][0]["caminho"] == "app.py"
    assert dados["achados"][0]["categoria"] == "security"


def test_hash_das_regras_vai_para_a_saida(tmp_path, monkeypatch):
    dados = executar(
        tmp_path,
        monkeypatch,
        lambda raiz, **kw: SaidaSemgrep(achados=(), hash_regras="fd16c10bc6b5"),
    )
    assert dados["hash_regras"] == "fd16c10bc6b5"


def test_erros_de_analise_vao_para_a_saida(tmp_path, monkeypatch):
    erro = {"arquivo": "a.tsx", "mensagem": "sintaxe"}
    dados = executar(
        tmp_path,
        monkeypatch,
        lambda raiz, **kw: SaidaSemgrep(achados=(), erros=(erro,)),
    )
    assert dados["erros_de_analise"] == [erro]


def test_caminho_do_achado_e_relativo_a_raiz_do_repo(tmp_path, monkeypatch):
    # Rede de segurança: se o scanner devolver caminho absoluto, a anotação do
    # Check Run ainda precisa do caminho relativo.
    dados = executar(
        tmp_path,
        monkeypatch,
        lambda raiz, **kw: SaidaSemgrep(
            achados=(Achado("r1", Severidade.ERRO, str(raiz / "app.py"), 1, 1, "achei"),)
        ),
    )
    assert dados["achados"][0]["caminho"] == "app.py"


def test_falha_do_scanner_vira_ok_false_e_nao_explode(tmp_path, monkeypatch):
    def explodir(raiz, **kw):
        raise SemgrepFalhou("semgrep saiu com 2")

    dados = executar(tmp_path, monkeypatch, explodir)

    assert dados["ok"] is False
    assert "semgrep" in dados["erro"]
    assert dados["achados"] == []


def test_erro_inesperado_tambem_vira_ok_false(tmp_path, monkeypatch):
    # Container que morre calado deixa o PR travado sem mensagem nenhuma.
    def explodir(raiz, **kw):
        raise ValueError("severidade CATASTROPHIC desconhecida")

    dados = executar(tmp_path, monkeypatch, explodir)

    assert dados["ok"] is False
    assert "ValueError" in dados["erro"]
    assert "CATASTROPHIC" in dados["erro"]


def test_pacote_ilegivel_vira_ok_false(tmp_path, monkeypatch):
    monkeypatch.setattr(analisador, "rodar", lambda raiz, **kw: SaidaSemgrep(achados=()))
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    (entrada / NOME_CONTEXTO).write_text("{}")
    saida = tmp_path / "saida"
    saida.mkdir()

    dados = json.loads(analisador.analisar(entrada, saida).read_text())

    assert dados["ok"] is False
    assert dados["erro"]


def test_escreve_semgrepignore_vazio_na_raiz(tmp_path, monkeypatch):
    # Sem isso, um `.semgrepignore` com `*` vindo no PR zera a análise inteira.
    visto = {}

    def espiar(raiz, **kw):
        arquivo = raiz / ".semgrepignore"
        visto["existe"] = arquivo.exists()
        visto["conteudo"] = arquivo.read_text() if arquivo.exists() else None
        return SaidaSemgrep(achados=())

    executar(tmp_path, monkeypatch, espiar)

    assert visto["existe"] is True
    assert visto["conteudo"] == ""


def test_semgrepignore_do_pacote_e_sobrescrito(tmp_path, monkeypatch):
    visto = {}

    def espiar(raiz, **kw):
        visto["conteudo"] = (raiz / ".semgrepignore").read_text()
        return SaidaSemgrep(achados=())

    monkeypatch.setattr(analisador, "rodar", espiar)
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    montar_tar(
        entrada,
        {
            "gabhrielv-hoppr-a1b2c3/app.py": "x = 1\n",
            "gabhrielv-hoppr-a1b2c3/.semgrepignore": "*\n",
        },
    )
    escrever_contexto(
        Contexto(owner="o", repo="r", head_sha="s", evento=Evento.PUSH),
        entrada / NOME_CONTEXTO,
    )
    saida = tmp_path / "saida"
    saida.mkdir()

    analisador.analisar(entrada, saida)

    assert visto["conteudo"] == ""


class S3Falso:
    def __init__(self, arquivos: dict[str, bytes] | None = None):
        self.arquivos = arquivos or {}
        self.enviados: dict[str, bytes] = {}

    def download_file(self, Bucket, Key, Filename):
        if Key not in self.arquivos:
            raise KeyError(Key)
        Path(Filename).write_bytes(self.arquivos[Key])

    def upload_file(self, Filename, Bucket, Key):
        self.enviados[Key] = Path(Filename).read_bytes()


def montar_s3(tmp_path: Path) -> S3Falso:
    entrada = montar_pacote(tmp_path)
    prefixo = "entrada/gabhrielv/hoppr/a1b2c3"
    return S3Falso(
        {
            f"{prefixo}/codigo.tar.gz": (entrada / "codigo.tar.gz").read_bytes(),
            f"{prefixo}/contexto.json": (entrada / "contexto.json").read_bytes(),
        }
    )


def test_handler_escreve_o_resultado_no_prefixo_de_saida(tmp_path, monkeypatch):
    s3 = montar_s3(tmp_path)
    monkeypatch.setattr(analisador, "_cliente_s3", lambda: s3)
    monkeypatch.setattr(
        analisador, "rodar", lambda raiz, **kw: SaidaSemgrep(achados=(), erros=())
    )

    analisador.lambda_handler(
        {"bucket": "b", "prefixo": "entrada/gabhrielv/hoppr/a1b2c3"}, None
    )

    assert "saida/gabhrielv/hoppr/a1b2c3/achados.json" in s3.enviados


def test_handler_devolve_achados_do_pacote(tmp_path, monkeypatch):
    s3 = montar_s3(tmp_path)
    monkeypatch.setattr(analisador, "_cliente_s3", lambda: s3)
    monkeypatch.setattr(
        analisador,
        "rodar",
        lambda raiz, **kw: SaidaSemgrep(
            achados=(Achado("r1", Severidade.ERRO, "app.py", 1, 1, "achei"),), erros=()
        ),
    )

    analisador.lambda_handler(
        {"bucket": "b", "prefixo": "entrada/gabhrielv/hoppr/a1b2c3"}, None
    )

    dados = json.loads(s3.enviados["saida/gabhrielv/hoppr/a1b2c3/achados.json"])
    assert dados["ok"] is True
    assert len(dados["achados"]) == 1


def test_handler_usa_tmp_que_e_o_unico_lugar_gravavel_da_lambda(tmp_path, monkeypatch):
    # O filesystem da imagem e so-leitura em producao. Escrever fora de /tmp
    # falha, e o erro nao diz que o problema foi esse.
    s3 = montar_s3(tmp_path)
    monkeypatch.setattr(analisador, "_cliente_s3", lambda: s3)
    monkeypatch.setattr(
        analisador, "rodar", lambda raiz, **kw: SaidaSemgrep(achados=(), erros=())
    )
    usados: list[str] = []
    original = analisador.tempfile.TemporaryDirectory

    def espiao(*a, **k):
        contexto = original(*a, **k)
        usados.append(contexto.name)
        return contexto

    monkeypatch.setattr(analisador.tempfile, "TemporaryDirectory", espiao)
    analisador.lambda_handler(
        {"bucket": "b", "prefixo": "entrada/gabhrielv/hoppr/a1b2c3"}, None
    )

    assert all(caminho.startswith("/tmp") for caminho in usados), usados
