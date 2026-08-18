import json
import tarfile
from pathlib import Path

import pytest
from dubles import ClienteFalso, ClienteQueFalha

from pra.investigadora import handler
from pra.llm.cliente import Chamada, CotaEsgotada, RespostaLLM

SHA = "a" * 40
PREFIXO_ENTRADA = f"entrada/gabhrielv/hoppr/{SHA}"
PREFIXO_SAIDA = f"saida/gabhrielv/hoppr/{SHA}"


class ContextoLambda:
    def __init__(self, restante_ms=600_000):
        self._restante = restante_ms

    def get_remaining_time_in_millis(self):
        return self._restante


def _achado(linha=2, regra="python.lang.security.audit.sqli", cwes=("89",)):
    return {
        "regra": regra,
        "severidade": "ERROR",
        "categoria": "security",
        "caminho": "app/db.py",
        "linha_inicio": linha,
        "linha_fim": linha,
        "mensagem": "possível SQL injection",
        "cwes": list(cwes),
    }


class S3Falso:
    """Guarda objetos em memória e escreve/lê arquivos como o boto3 faria."""

    def __init__(self, objetos: dict[str, bytes]):
        self.objetos = dict(objetos)
        self.escritos: dict[str, bytes] = {}

    def get_object(self, Bucket, Key):
        class Corpo:
            def __init__(self, dados):
                self._dados = dados

            def read(self):
                return self._dados

        return {"Body": Corpo(self.objetos[Key])}

    def download_file(self, Bucket, Key, Filename):
        Path(Filename).write_bytes(self.objetos[Key])

    def upload_file(self, Filename, Bucket, Key):
        self.escritos[Key] = Path(Filename).read_bytes()


@pytest.fixture
def s3(tmp_path, monkeypatch):
    codigo = tmp_path / "repo" / "app"
    codigo.mkdir(parents=True)
    (codigo / "db.py").write_text(
        "def por_id(identificador):\n    return 'SELECT ' + identificador\n"
    )
    tar = tmp_path / "codigo.tar.gz"
    with tarfile.open(tar, "w:gz") as arquivo:
        arquivo.add(tmp_path / "repo", arcname="repo")

    contexto = {
        "owner": "gabhrielv",
        "repo": "hoppr",
        "head_sha": SHA,
        "evento": "pull_request",
        "numero_pr": 7,
        "base_sha": None,
        "tudo_novo": False,
        "linhas_tocadas": {"app/db.py": [[1, 5]]},
    }
    achados = {"ok": True, "hash_regras": "abc123", "achados": [_achado()]}

    falso = S3Falso(
        {
            f"{PREFIXO_ENTRADA}/codigo.tar.gz": tar.read_bytes(),
            f"{PREFIXO_ENTRADA}/contexto.json": json.dumps(contexto).encode(),
            f"{PREFIXO_SAIDA}/achados.json": json.dumps(achados).encode(),
        }
    )
    monkeypatch.setattr(handler, "_cliente_s3", lambda: falso)
    monkeypatch.setenv("PRA_PARAM_CHAVE_LLM", "/pra/llm/chave")
    monkeypatch.setenv("PRA_PARAM_MODELO_LLM", "/pra/llm/modelo")
    return falso


def _evento():
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "pacotes"},
                    "object": {"key": f"{PREFIXO_SAIDA}/achados.json"},
                }
            }
        ]
    }


def _concluir(entrada="nao"):
    return RespostaLLM(
        chamadas=(
            Chamada(
                nome="concluir",
                argumentos={
                    "entrada_controlavel": entrada,
                    "sanitizacao_encontrada": "nao_sei",
                    "raciocinio": "vem de enum",
                },
            ),
        ),
        tokens=100,
    )


def _escrito(s3):
    return json.loads(s3.escritos[f"{PREFIXO_SAIDA}/evidencias.json"])


def test_investiga_o_bloqueante_e_grava_a_evidencia(s3, monkeypatch):
    monkeypatch.setattr(handler, "_cliente_llm", lambda: ClienteFalso([_concluir()]))
    handler.lambda_handler(_evento(), ContextoLambda())

    dados = _escrito(s3)
    assert dados["ok"] is True
    assert dados["degradado"] is False
    assert len(dados["evidencias"]) == 1
    assert dados["evidencias"][0]["entrada_controlavel"] == "nao"


def test_o_modelo_que_julgou_vai_para_a_evidencia(s3, monkeypatch):
    """Sem isto a auditoria da D11 não separa troca de modelo de troca de
    prompt, e a comparação de modelos do marco 4 não teria com o que comparar."""
    monkeypatch.setattr(
        handler,
        "_cliente_llm",
        lambda: ClienteFalso([_concluir()], modelo="modelo-x"),
    )
    handler.lambda_handler(_evento(), ContextoLambda())
    assert _escrito(s3)["modelo"] == "modelo-x"


def test_degradado_ainda_registra_o_modelo_tentado(s3, monkeypatch):
    monkeypatch.setattr(
        handler,
        "_cliente_llm",
        lambda: ClienteQueFalha(CotaEsgotada("acabou"), modelo="modelo-x"),
    )
    handler.lambda_handler(_evento(), ContextoLambda())

    dados = _escrito(s3)
    assert dados["degradado"] is True
    assert dados["modelo"] == "modelo-x"


def test_achado_preexistente_nao_gasta_token(s3, monkeypatch):
    """Pré-triar com a regra é o que impede pagar por achado que não bloqueia."""
    contexto = json.loads(s3.objetos[f"{PREFIXO_ENTRADA}/contexto.json"])
    contexto["linhas_tocadas"] = {"app/db.py": [[90, 99]]}
    s3.objetos[f"{PREFIXO_ENTRADA}/contexto.json"] = json.dumps(contexto).encode()
    monkeypatch.setattr(handler, "_cliente_llm", lambda: ClienteFalso([]))

    handler.lambda_handler(_evento(), ContextoLambda())
    assert _escrito(s3)["evidencias"] == []


def test_cota_esgotada_grava_degradado(s3, monkeypatch):
    monkeypatch.setattr(
        handler, "_cliente_llm", lambda: ClienteQueFalha(CotaEsgotada("acabou"))
    )
    handler.lambda_handler(_evento(), ContextoLambda())

    dados = _escrito(s3)
    assert dados["degradado"] is True
    assert "acabou" in dados["motivo"]
    assert dados["evidencias"] == []


def test_watchdog_para_quando_o_tempo_acaba(s3, monkeypatch):
    monkeypatch.setattr(handler, "_cliente_llm", lambda: ClienteFalso([]))
    handler.lambda_handler(_evento(), ContextoLambda(restante_ms=1_000))

    dados = _escrito(s3)
    assert dados["nao_investigados"] == 1
    assert dados["evidencias"] == []


def test_analise_que_falhou_nao_investiga_mas_acorda_a_publicadora(s3, monkeypatch):
    s3.objetos[f"{PREFIXO_SAIDA}/achados.json"] = json.dumps(
        {"ok": False, "erro": "semgrep morreu", "achados": []}
    ).encode()
    monkeypatch.setattr(handler, "_cliente_llm", lambda: ClienteFalso([]))

    handler.lambda_handler(_evento(), ContextoLambda())
    assert f"{PREFIXO_SAIDA}/evidencias.json" in s3.escritos


def test_erro_inesperado_ainda_escreve_o_arquivo(s3, monkeypatch):
    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "_cliente_llm", explode)
    handler.lambda_handler(_evento(), ContextoLambda())

    dados = _escrito(s3)
    assert dados["ok"] is False
    assert dados["degradado"] is True
    assert "boom" in dados["motivo"]


def test_teto_de_achados_por_analise(s3, monkeypatch):
    achados = {
        "ok": True,
        "hash_regras": "abc123",
        "achados": [_achado(linha=1, regra=f"regra-{i}") for i in range(15)],
    }
    s3.objetos[f"{PREFIXO_SAIDA}/achados.json"] = json.dumps(achados).encode()
    monkeypatch.setattr(
        handler,
        "_cliente_llm",
        lambda: ClienteFalso([_concluir() for _ in range(handler.TETO_ACHADOS)]),
    )

    handler.lambda_handler(_evento(), ContextoLambda())
    dados = _escrito(s3)
    assert len(dados["evidencias"]) == handler.TETO_ACHADOS
    assert dados["nao_investigados"] == 15 - handler.TETO_ACHADOS


def test_ordem_de_investigacao_e_estavel(s3, monkeypatch):
    """Quando há mais bloqueantes que o teto, a ordem decide QUAIS entram.
    Reanalisar o mesmo commit precisa investigar os mesmos."""
    achados = {
        "ok": True,
        "hash_regras": "abc123",
        "achados": [
            {**_achado(linha=3, regra="z-regra"), "caminho": "app/db.py"},
            {**_achado(linha=1, regra="a-regra"), "caminho": "app/db.py"},
        ],
    }
    s3.objetos[f"{PREFIXO_SAIDA}/achados.json"] = json.dumps(achados).encode()
    monkeypatch.setattr(
        handler, "_cliente_llm", lambda: ClienteFalso([_concluir(), _concluir()])
    )

    handler.lambda_handler(_evento(), ContextoLambda())
    chaves = [e["chave"] for e in _escrito(s3)["evidencias"]]
    assert chaves[0].endswith("|app/db.py|1|1")


def test_achado_fora_de_fluxo_nao_gasta_token(s3, monkeypatch):
    """A pré-tria é por CWE também: pagar token para o modelo julgar uma
    credencial escrita no código é gastar cota numa pergunta sem resposta."""
    resultado = json.loads(s3.objetos[f"{PREFIXO_SAIDA}/achados.json"])
    resultado["achados"] = [_achado(cwes=("798",))]
    s3.objetos[f"{PREFIXO_SAIDA}/achados.json"] = json.dumps(resultado).encode()
    monkeypatch.setattr(handler, "_cliente_llm", lambda: ClienteFalso([]))

    handler.lambda_handler(_evento(), ContextoLambda())
    assert _escrito(s3)["evidencias"] == []
