import json

import pytest

from portcullis.consulta import handler as consulta

SHA = "c085f4f65222ba3a6722791d09d11250f70ef5e7"


class TabelaFalsa:
    def __init__(self, itens=None):
        self.itens = itens or {}
        self.consultas: list[dict] = []

    def get_item(self, Key):
        self.consultas.append(Key)
        item = self.itens.get((Key["repo"], Key["sha"]))
        return {"Item": item} if item else {}


def registro(veredito="liberado"):
    return {
        "repo": "gabhrielv#hoppr",
        "sha": SHA,
        "veredito": veredito,
        "versao_regra": "2",
        "hash_regras": "fd16c10bc6b5",
        "horario": "2026-08-14T19:41:54+00:00",
    }


@pytest.fixture
def tabela(monkeypatch):
    falsa = TabelaFalsa()
    monkeypatch.setattr(consulta, "_tabela", lambda nome: falsa)
    monkeypatch.setenv("PORTCULLIS_TABELA", "portcullis-auditoria")
    return falsa


def pedir(owner="gabhrielv", repo="hoppr", sha=SHA):
    return {"pathParameters": {"owner": owner, "repo": repo, "sha": sha}}


def corpo(resposta):
    return json.loads(resposta["body"])


def test_sha_liberado_responde_200(tabela):
    tabela.itens[("gabhrielv#hoppr", SHA)] = registro("liberado")
    resposta = consulta.lambda_handler(pedir(), None)

    assert resposta["statusCode"] == 200
    assert corpo(resposta)["liberado"] is True
    assert corpo(resposta)["versao_regra"] == "2"


def test_sha_bloqueado_responde_403(tabela):
    tabela.itens[("gabhrielv#hoppr", SHA)] = registro("bloqueado")
    resposta = consulta.lambda_handler(pedir(), None)

    assert resposta["statusCode"] == 403
    assert corpo(resposta)["liberado"] is False


def test_sha_desconhecido_responde_404_e_nao_libera(tabela):
    # É este o caso que cobre push direto e bypass de administrador: commit
    # que nunca foi analisado não tem registro, e não ter registro reprova.
    resposta = consulta.lambda_handler(pedir(sha="0" * 40), None)

    assert resposta["statusCode"] == 404
    assert corpo(resposta)["liberado"] is False


def test_analise_que_nao_concluiu_nao_libera(tabela):
    # `nao_conclui` não é `liberado`. Não saber tem que reprovar.
    tabela.itens[("gabhrielv#hoppr", SHA)] = registro("nao_conclui")
    resposta = consulta.lambda_handler(pedir(), None)

    assert resposta["statusCode"] == 403
    assert corpo(resposta)["liberado"] is False


def test_parametro_faltando_responde_400(tabela):
    resposta = consulta.lambda_handler({"pathParameters": {"owner": "gabhrielv"}}, None)
    assert resposta["statusCode"] == 400


def test_evento_sem_parametros_nao_estoura(tabela):
    assert consulta.lambda_handler({}, None)["statusCode"] == 400


def test_o_lock_de_deduplicacao_nunca_e_confundido_com_veredito(tabela):
    # Lock e veredito moram na mesma tabela, distinguidos pela chave de
    # ordenação. Um lock sem análise concluída precisa dar 404, não liberar.
    tabela.itens[("gabhrielv#hoppr", f"lock#{SHA}")] = {"repo": "x", "sha": "y"}
    resposta = consulta.lambda_handler(pedir(), None)

    assert resposta["statusCode"] == 404
    assert corpo(resposta)["liberado"] is False


def test_a_consulta_usa_a_chave_composta_do_repositorio(tabela):
    tabela.itens[("gabhrielv#hoppr", SHA)] = registro()
    consulta.lambda_handler(pedir(), None)

    assert tabela.consultas[0] == {"repo": "gabhrielv#hoppr", "sha": SHA}


def test_resposta_nao_carrega_a_lista_de_achados(tabela):
    # O endpoint é público. Ele responde se passou, não o que foi encontrado —
    # detalhe de vulnerabilidade não vaza para quem só sabe um SHA.
    tabela.itens[("gabhrielv#hoppr", SHA)] = {
        **registro("bloqueado"),
        "bloqueantes": [{"regra": "sqli", "caminho": "app/segredo.py"}],
    }
    resposta = consulta.lambda_handler(pedir(), None)

    assert "segredo.py" not in resposta["body"]
    assert "bloqueantes" not in corpo(resposta)
