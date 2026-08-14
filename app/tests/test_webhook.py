import base64
import hashlib
import hmac
import json
import logging

import pytest

from portcullis.config import obrigatoria
from portcullis.webhook import handler as webhook

SEGREDO = "segredo-de-teste"
FILA = "https://sqs.us-east-1.amazonaws.com/1/portcullis-analises"

REPOSITORIO = {
    "name": "hoppr",
    "owner": {"login": "gabhrielv"},
    "default_branch": "main",
}


class FilaFalsa:
    """Dublê do cliente do SQS. Guarda o que foi enviado para o teste conferir."""

    def __init__(self):
        self.enviadas: list[dict] = []

    # Nomes em PascalCase porque é a assinatura do boto3, não uma escolha.
    def send_message(self, QueueUrl: str, MessageBody: str):
        self.enviadas.append({"url": QueueUrl, "corpo": json.loads(MessageBody)})
        return {"MessageId": "1"}


@pytest.fixture
def fila(monkeypatch):
    falsa = FilaFalsa()
    monkeypatch.setattr(webhook, "_cliente_sqs", lambda: falsa)
    monkeypatch.setattr(webhook, "parametro_ssm", lambda nome: SEGREDO)
    monkeypatch.setenv("PORTCULLIS_FILA_URL", FILA)
    monkeypatch.setenv("PORTCULLIS_PARAM_SEGREDO_WEBHOOK", "/portcullis/github/segredo-webhook")
    return falsa


def evento(corpo: dict, nome_evento: str, segredo: str = SEGREDO, base64_: bool = False):
    bruto = json.dumps(corpo).encode()
    digest = hmac.new(segredo.encode(), bruto, hashlib.sha256).hexdigest()
    return {
        "body": base64.b64encode(bruto).decode() if base64_ else bruto.decode(),
        "isBase64Encoded": base64_,
        "headers": {
            "x-hub-signature-256": f"sha256={digest}",
            "x-github-event": nome_evento,
        },
    }


def corpo_de_pr(acao: str = "opened"):
    return {
        "action": acao,
        "number": 7,
        "repository": REPOSITORIO,
        "pull_request": {"head": {"sha": "aaa111"}, "base": {"sha": "bbb222"}},
    }


def corpo_de_push(ref: str = "refs/heads/main", deleted: bool = False):
    return {
        "ref": ref,
        "before": "bbb222",
        "after": "aaa111",
        "deleted": deleted,
        "repository": REPOSITORIO,
    }


def test_obrigatoria_recusa_variavel_ausente(monkeypatch):
    monkeypatch.delenv("PORTCULLIS_INEXISTENTE", raising=False)
    with pytest.raises(RuntimeError):
        obrigatoria("PORTCULLIS_INEXISTENTE")


def test_obrigatoria_trata_string_vazia_como_ausente(monkeypatch):
    monkeypatch.setenv("PORTCULLIS_VAZIA", "")
    with pytest.raises(RuntimeError):
        obrigatoria("PORTCULLIS_VAZIA")


def test_assinatura_invalida_devolve_401_e_nao_enfileira(fila):
    resposta = webhook.lambda_handler(
        evento(corpo_de_pr(), "pull_request", segredo="outro"), None
    )
    assert resposta["statusCode"] == 401
    assert fila.enviadas == []


def test_corpo_em_base64_e_decodificado_antes_de_conferir_o_hmac(fila):
    # O API Gateway pode entregar o corpo em base64. O HMAC do GitHub é sobre
    # os bytes originais: assinar a string base64 faz TODA requisição legítima
    # devolver 401 e nenhuma análise acontecer.
    resposta = webhook.lambda_handler(
        evento(corpo_de_pr(), "pull_request", base64_=True), None
    )
    assert resposta["statusCode"] == 200
    assert len(fila.enviadas) == 1


def test_cabecalho_em_caixa_alta_e_reconhecido(fila):
    bruto = evento(corpo_de_pr(), "pull_request")
    bruto["headers"] = {
        "X-Hub-Signature-256": bruto["headers"]["x-hub-signature-256"],
        "X-GitHub-Event": "pull_request",
    }
    resposta = webhook.lambda_handler(bruto, None)
    assert resposta["statusCode"] == 200
    assert len(fila.enviadas) == 1


def test_ping_responde_sem_enfileirar(fila):
    resposta = webhook.lambda_handler(evento({"zen": "oi"}, "ping"), None)
    assert resposta["statusCode"] == 200
    assert fila.enviadas == []


def test_evento_fora_da_lista_e_ignorado(fila):
    resposta = webhook.lambda_handler(evento({"qualquer": 1}, "issues"), None)
    assert resposta["statusCode"] == 200
    assert fila.enviadas == []


def test_pull_request_aberto_enfileira_o_trabalho(fila):
    webhook.lambda_handler(evento(corpo_de_pr("opened"), "pull_request"), None)

    assert len(fila.enviadas) == 1
    enviada = fila.enviadas[0]
    assert enviada["url"] == FILA
    assert enviada["corpo"] == {
        "owner": "gabhrielv",
        "repo": "hoppr",
        "evento": "pull_request",
        "head_sha": "aaa111",
        "base_sha": "bbb222",
        "numero_pr": 7,
    }


@pytest.mark.parametrize("acao", ["synchronize", "reopened"])
def test_pull_request_atualizado_ou_reaberto_tambem_enfileira(fila, acao):
    webhook.lambda_handler(evento(corpo_de_pr(acao), "pull_request"), None)
    assert len(fila.enviadas) == 1


@pytest.mark.parametrize("acao", ["closed", "labeled", "assigned"])
def test_acao_de_pr_que_nao_muda_codigo_nao_enfileira(fila, acao):
    resposta = webhook.lambda_handler(evento(corpo_de_pr(acao), "pull_request"), None)
    assert resposta["statusCode"] == 200
    assert fila.enviadas == []


def test_push_na_branch_padrao_enfileira(fila):
    webhook.lambda_handler(evento(corpo_de_push(), "push"), None)

    assert fila.enviadas[0]["corpo"] == {
        "owner": "gabhrielv",
        "repo": "hoppr",
        "evento": "push",
        "head_sha": "aaa111",
        "base_sha": "bbb222",
        "numero_pr": None,
    }


def test_push_fora_da_branch_padrao_nao_enfileira(fila):
    # A branch do PR já é analisada pelo evento de pull_request; analisar de
    # novo aqui seria pagar duas vezes pelo mesmo commit.
    webhook.lambda_handler(evento(corpo_de_push(ref="refs/heads/feature"), "push"), None)
    assert fila.enviadas == []


def test_push_de_delecao_de_branch_nao_enfileira(fila):
    # Não existe código para analisar, e `after` vem zerado.
    webhook.lambda_handler(evento(corpo_de_push(deleted=True), "push"), None)
    assert fila.enviadas == []


def test_push_de_tag_nao_enfileira(fila):
    webhook.lambda_handler(evento(corpo_de_push(ref="refs/tags/v1.0"), "push"), None)
    assert fila.enviadas == []


def test_enfileiramento_e_registrado_com_repo_e_sha(fila, caplog):
    caplog.set_level(logging.INFO)
    webhook.lambda_handler(evento(corpo_de_pr(), "pull_request"), None)

    registro = caplog.text
    assert "gabhrielv/hoppr" in registro
    assert "aaa111" in registro


def test_assinatura_invalida_e_registrada_como_aviso(fila, caplog):
    caplog.set_level(logging.INFO)
    webhook.lambda_handler(evento(corpo_de_pr(), "pull_request", segredo="outro"), None)

    assert any(r.levelno >= logging.WARNING for r in caplog.records)
    assert "assinatura" in caplog.text.lower()


def test_evento_descartado_registra_o_motivo(fila, caplog):
    caplog.set_level(logging.INFO)
    webhook.lambda_handler(evento(corpo_de_push(ref="refs/heads/outra"), "push"), None)

    assert caplog.records, "descarte silencioso: nada foi registrado"


def test_log_nunca_carrega_texto_escrito_por_quem_abriu_o_pr(fila, caplog):
    # Titulo e descricao sao texto livre de terceiro — vetor de injecao de
    # prompt no marco 2, e de forja de linha de log agora. Nao entram.
    caplog.set_level(logging.INFO)
    corpo = corpo_de_pr()
    corpo["pull_request"]["title"] = "TITULO-PLANTADO-XYZ"
    corpo["pull_request"]["body"] = "CORPO-PLANTADO-XYZ"

    webhook.lambda_handler(evento(corpo, "pull_request"), None)

    assert "PLANTADO" not in caplog.text


def test_nome_de_evento_hostil_nao_forja_linha_de_log(fila, caplog):
    # O cabecalho vem de quem chamou e ainda nao foi autenticado: uma quebra
    # de linha ali escreveria uma linha de log inteira, inventada.
    caplog.set_level(logging.INFO)
    bruto = evento(corpo_de_pr(), "pull_request", segredo="outro")
    bruto["headers"]["x-github-event"] = "push\nINFO enfileirado repo=falso/falso"

    webhook.lambda_handler(bruto, None)

    assert "falso/falso" not in caplog.text
