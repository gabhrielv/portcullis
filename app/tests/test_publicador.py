import json

import pytest

from portcullis.publicador import handler as publicador

BUCKET = "portcullis-pacotes-1"
SHA = "aaa111"
PREFIXO_SAIDA = f"saida/gabhrielv/hoppr/{SHA}"
PREFIXO_ENTRADA = f"entrada/gabhrielv/hoppr/{SHA}"

CONTEXTO = {
    "owner": "gabhrielv",
    "repo": "hoppr",
    "head_sha": SHA,
    "evento": "pull_request",
    "numero_pr": 7,
    "base_sha": "bbb222",
    "tudo_novo": False,
    "linhas_tocadas": {"app.py": [[10, 12]]},
}


def achados(ok=True, erro=None, lista=None):
    return {
        "ok": ok,
        "erro": erro,
        "owner": "gabhrielv",
        "repo": "hoppr",
        "head_sha": SHA,
        "hash_regras": "fd16c10bc6b5",
        "erros": [],
        "achados": lista if lista is not None else [],
    }


def achado(linha: int, severidade="ERROR", categoria="security", caminho="app.py"):
    return {
        "regra": "regra.x",
        "severidade": severidade,
        "categoria": categoria,
        "caminho": caminho,
        "linha_inicio": linha,
        "linha_fim": linha,
        "mensagem": "achei",
    }


class S3Falso:
    def __init__(self, objetos):
        self.objetos = objetos

    def get_object(self, Bucket, Key):
        return {"Body": FluxoFalso(self.objetos[Key])}


class FluxoFalso:
    def __init__(self, dados):
        self._dados = dados

    def read(self):
        return json.dumps(self._dados).encode()


class GithubFalso:
    def __init__(self):
        self.publicados: list[dict] = []

    def __call__(self, token, owner, repo, sha, veredito):
        self.publicados.append(
            {"owner": owner, "repo": repo, "sha": sha, "veredito": veredito}
        )


class AuditoriaFalsa:
    def __init__(self):
        self.registros: list[dict] = []

    def __call__(self, **kw):
        self.registros.append(kw)


@pytest.fixture
def nuvem(monkeypatch):
    github, auditoria = GithubFalso(), AuditoriaFalsa()
    monkeypatch.setattr(publicador, "publicar", github)
    monkeypatch.setattr(publicador, "gravar_auditoria", auditoria)
    monkeypatch.setattr(publicador, "parametro_ssm", lambda nome: "chave-pem")
    monkeypatch.setattr(publicador, "token_de_instalacao", lambda *a, **k: "ghs_t")
    monkeypatch.setenv("PORTCULLIS_TABELA", "portcullis-auditoria")
    monkeypatch.setenv("PORTCULLIS_GITHUB_APP_ID", "4589712")
    monkeypatch.setenv("PORTCULLIS_PARAM_CHAVE_APP", "/portcullis/github/chave-privada")
    return github, auditoria


def preparar(monkeypatch, dados_achados):
    s3 = S3Falso(
        {
            f"{PREFIXO_SAIDA}/achados.json": dados_achados,
            f"{PREFIXO_ENTRADA}/contexto.json": CONTEXTO,
        }
    )
    monkeypatch.setattr(publicador, "_cliente_s3", lambda: s3)
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": BUCKET},
                    "object": {"key": f"{PREFIXO_SAIDA}/achados.json"},
                }
            }
        ]
    }


def test_achado_em_linha_tocada_bloqueia(nuvem, monkeypatch):
    github, _ = nuvem
    evento = preparar(monkeypatch, achados(lista=[achado(11)]))

    publicador.lambda_handler(evento, None)

    veredito = github.publicados[0]["veredito"]
    assert veredito.estado.value == "bloqueado"
    assert len(veredito.bloqueantes) == 1


def test_achado_fora_do_diff_e_preexistente_e_libera(nuvem, monkeypatch):
    github, _ = nuvem
    evento = preparar(monkeypatch, achados(lista=[achado(500)]))

    publicador.lambda_handler(evento, None)

    veredito = github.publicados[0]["veredito"]
    assert veredito.estado.value == "liberado"
    assert len(veredito.preexistentes) == 1


def test_analise_que_falhou_vira_nao_conclui(nuvem, monkeypatch):
    # ok:false NAO pode virar success: o portao nao sabe se ha problema, e
    # nao saber tem que bloquear.
    github, _ = nuvem
    evento = preparar(monkeypatch, achados(ok=False, erro="semgrep saiu com 2"))

    publicador.lambda_handler(evento, None)

    veredito = github.publicados[0]["veredito"]
    assert veredito.estado.value == "nao_conclui"
    assert "semgrep" in veredito.motivo


def test_auditoria_guarda_a_impressao_digital_das_regras(nuvem, monkeypatch):
    # Sem isso, mudanca no conjunto de regras fica indistinguivel de mudanca
    # no agente, no marco 2.
    _, auditoria = nuvem
    evento = preparar(monkeypatch, achados(lista=[achado(11)]))

    publicador.lambda_handler(evento, None)

    registro = auditoria.registros[0]
    assert registro["hash_regras"] == "fd16c10bc6b5"
    assert registro["sha"] == SHA
    assert registro["repo"] == "gabhrielv#hoppr"


def test_auditoria_e_gravada_mesmo_quando_libera(nuvem, monkeypatch):
    # A pergunta que a auditoria responde e "por que esse deploy passou",
    # entao o caso liberado e justamente o que precisa estar la.
    _, auditoria = nuvem
    evento = preparar(monkeypatch, achados(lista=[]))

    publicador.lambda_handler(evento, None)

    assert len(auditoria.registros) == 1
    assert auditoria.registros[0]["veredito"].estado.value == "liberado"


def test_warning_de_seguranca_em_linha_tocada_bloqueia(nuvem, monkeypatch):
    # VERSAO_REGRA 2: severidade do semgrep nao mede risco, entao WARNING com
    # categoria security tambem trava.
    github, _ = nuvem
    evento = preparar(
        monkeypatch, achados(lista=[achado(11, severidade="WARNING")])
    )

    publicador.lambda_handler(evento, None)

    assert github.publicados[0]["veredito"].estado.value == "bloqueado"


def test_warning_de_performance_em_linha_tocada_nao_bloqueia(nuvem, monkeypatch):
    github, _ = nuvem
    evento = preparar(
        monkeypatch,
        achados(lista=[achado(11, severidade="WARNING", categoria="performance")]),
    )

    publicador.lambda_handler(evento, None)

    veredito = github.publicados[0]["veredito"]
    assert veredito.estado.value == "liberado"
    assert len(veredito.avisos) == 1
