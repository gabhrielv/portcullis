import io
import json

import pytest

from portcullis.buscador import handler as buscador
from portcullis.buscador.github_api import (
    RepositorioGrandeDemais,
    fluxo_com_teto,
)
from portcullis.modelos import FaixaLinhas

BUCKET = "pra-pacotes-1"
FUNCAO = "portcullis-analisador"
TABELA = "pra-auditoria"

TRABALHO_PR = {
    "owner": "gabhrielv",
    "repo": "hoppr",
    "evento": "pull_request",
    "head_sha": "aaa111",
    "base_sha": "bbb222",
    "numero_pr": 7,
}
TRABALHO_PUSH = {
    "owner": "gabhrielv",
    "repo": "hoppr",
    "evento": "push",
    "head_sha": "aaa111",
    "base_sha": "0" * 40,
    "numero_pr": None,
}


class S3Falso:
    def __init__(self):
        self.objetos: dict[str, bytes] = {}

    def upload_fileobj(self, fluxo, Bucket, Key):
        self.objetos[Key] = fluxo.read()

    def put_object(self, Bucket, Key, Body):
        self.objetos[Key] = Body if isinstance(Body, bytes) else Body.encode()


class DynamoFalso:
    def __init__(self, ja_existentes=()):
        self.itens: set[tuple[str, str]] = set(ja_existentes)
        self.tentativas: list[tuple[str, str]] = []

    def put_item(self, TableName, Item, ConditionExpression):
        chave = (Item["repo"]["S"], Item["sha"]["S"])
        self.tentativas.append(chave)
        if chave in self.itens:
            raise self.exceptions.ConditionalCheckFailedException("ja existe")
        self.itens.add(chave)

    def delete_item(self, TableName, Key):
        self.itens.discard((Key["repo"]["S"], Key["sha"]["S"]))

    class exceptions:
        class ConditionalCheckFailedException(Exception):
            pass


class LambdaFalsa:
    def __init__(self):
        self.invocacoes: list[dict] = []

    def invoke(self, FunctionName, InvocationType, Payload):
        self.invocacoes.append(
            {
                "funcao": FunctionName,
                "tipo": InvocationType,
                "carga": json.loads(Payload),
            }
        )


@pytest.fixture
def nuvem(monkeypatch):
    s3, dynamo, lamb = S3Falso(), DynamoFalso(), LambdaFalsa()
    monkeypatch.setattr(buscador, "_cliente_s3", lambda: s3)
    monkeypatch.setattr(buscador, "_cliente_dynamo", lambda: dynamo)
    monkeypatch.setattr(buscador, "_cliente_lambda", lambda: lamb)
    monkeypatch.setattr(buscador, "parametro_ssm", lambda nome: "chave-pem-falsa")
    monkeypatch.setattr(
        buscador, "token_de_instalacao", lambda *a, **k: "ghs_token"
    )
    monkeypatch.setattr(
        buscador,
        "tarball_para_s3",
        lambda token, owner, repo, sha, bucket, chave: s3.put_object(
            Bucket=bucket, Key=chave, Body=b"tarball"
        ),
    )
    monkeypatch.setattr(
        buscador,
        "linhas_tocadas_de_pr",
        lambda *a, **k: ({"app.py": (FaixaLinhas(10, 12),)}, False),
    )
    monkeypatch.setattr(
        buscador, "linhas_tocadas_de_push", lambda *a, **k: ({}, True)
    )
    monkeypatch.setenv("PORTCULLIS_BUCKET_PACOTES", BUCKET)
    monkeypatch.setenv("PORTCULLIS_FUNCAO_ANALISADOR", FUNCAO)
    monkeypatch.setenv("PORTCULLIS_TABELA", TABELA)
    monkeypatch.setenv("PORTCULLIS_GITHUB_APP_ID", "4589712")
    monkeypatch.setenv("PORTCULLIS_PARAM_CHAVE_APP", "/portcullis/github/chave-privada")
    return s3, dynamo, lamb


def sqs(trabalho: dict) -> dict:
    return {"Records": [{"body": json.dumps(trabalho)}]}


def test_fluxo_com_teto_deixa_passar_o_que_cabe():
    fluxo = fluxo_com_teto(io.BytesIO(b"12345"), teto=10)
    assert fluxo.read() == b"12345"


def test_fluxo_com_teto_estoura_sem_bufferizar_tudo():
    # Streaming: o teto vale enquanto os bytes chegam, nao depois de carregar
    # o repositorio inteiro na memoria da Lambda.
    fluxo = fluxo_com_teto(io.BytesIO(b"x" * 100), teto=10)
    with pytest.raises(RepositorioGrandeDemais):
        fluxo.read()


def test_pacote_ganha_codigo_e_contexto_no_prefixo_do_sha(nuvem):
    s3, _, _ = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    prefixo = "entrada/gabhrielv/hoppr/aaa111"
    assert f"{prefixo}/codigo.tar.gz" in s3.objetos
    assert f"{prefixo}/contexto.json" in s3.objetos


def test_contexto_carrega_as_linhas_tocadas_do_pr(nuvem):
    s3, _, _ = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    ctx = json.loads(s3.objetos["entrada/gabhrielv/hoppr/aaa111/contexto.json"])
    assert ctx["linhas_tocadas"] == {"app.py": [[10, 12]]}
    assert ctx["numero_pr"] == 7
    assert ctx["tudo_novo"] is False


def test_push_com_base_zerada_marca_tudo_como_novo(nuvem):
    s3, _, _ = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PUSH), None)

    ctx = json.loads(s3.objetos["entrada/gabhrielv/hoppr/aaa111/contexto.json"])
    assert ctx["tudo_novo"] is True


def test_analisador_e_invocado_de_forma_assincrona(nuvem):
    _, _, lamb = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert len(lamb.invocacoes) == 1
    invocacao = lamb.invocacoes[0]
    assert invocacao["funcao"] == FUNCAO
    # Event = assincrono. RequestResponse faria a buscadora esperar ~2 min
    # pagando por duas Lambdas ao mesmo tempo.
    assert invocacao["tipo"] == "Event"
    assert invocacao["carga"]["prefixo"] == "entrada/gabhrielv/hoppr/aaa111"


def test_mensagem_repetida_nao_gera_segunda_analise(nuvem):
    _, _, lamb = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)
    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert len(lamb.invocacoes) == 1, "a duplicata virou uma segunda analise"


def test_o_lock_da_duplicata_usa_o_sha_como_chave(nuvem):
    _, dynamo, _ = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert ("gabhrielv#hoppr", "lock#aaa111") in dynamo.itens


def test_sha_diferente_no_mesmo_repo_gera_analise_propria(nuvem):
    _, _, lamb = nuvem
    buscador.lambda_handler(sqs(TRABALHO_PR), None)
    outro = dict(TRABALHO_PR, head_sha="ccc333")
    buscador.lambda_handler(sqs(outro), None)

    assert len(lamb.invocacoes) == 2


def test_pacote_nunca_carrega_texto_escrito_por_quem_abriu_o_pr(nuvem):
    # O analisador le o pacote e so o pacote. Titulo e descricao sao texto
    # livre de terceiro: o que nao entra aqui, o agente do marco 2 nao ve.
    s3, _, _ = nuvem
    trabalho = dict(TRABALHO_PR, titulo="TITULO-PLANTADO", corpo="CORPO-PLANTADO")
    buscador.lambda_handler(sqs(trabalho), None)

    tudo = b"".join(s3.objetos.values())
    assert b"PLANTADO" not in tudo


def test_falha_no_meio_libera_o_lock_para_a_reentrega(nuvem, monkeypatch):
    # Sem isto a falha vira silencio: o SQS reentrega, a reentrega cai no lock,
    # pula, devolve sucesso — e nenhuma analise acontece sem nada avisar.
    _, dynamo, lamb = nuvem

    def explodir(*a, **k):
        raise RepositorioGrandeDemais("400 MB")

    monkeypatch.setattr(buscador, "tarball_para_s3", explodir)

    with pytest.raises(RepositorioGrandeDemais):
        buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert ("gabhrielv#hoppr", "lock#aaa111") not in dynamo.itens
    assert lamb.invocacoes == []


def test_falha_ao_disparar_a_analise_tambem_libera_o_lock(nuvem, monkeypatch):
    # O pacote existir no S3 nao adianta se a analise nunca foi disparada.
    # A reentrega precisa poder tentar de novo.
    _, dynamo, lamb = nuvem

    def explodir(**k):
        raise RuntimeError("funcao do analisador nao existe")

    monkeypatch.setattr(lamb, "invoke", explodir)

    with pytest.raises(RuntimeError):
        buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert ("gabhrielv#hoppr", "lock#aaa111") not in dynamo.itens


def test_checagem_abre_como_em_progresso_ao_montar_o_pacote(nuvem, monkeypatch):
    # A analise leva ~4 min. Sem isto o PR fica esse tempo todo sem sinal
    # nenhum, e o desenvolvedor assume que quebrou alguma coisa.
    abertas: list[tuple] = []
    monkeypatch.setattr(
        buscador,
        "criar_em_progresso",
        lambda token, owner, repo, sha: abertas.append((owner, repo, sha)),
    )

    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert abertas == [("gabhrielv", "hoppr", "aaa111")]


def test_falha_ao_abrir_a_checagem_nao_impede_a_analise(nuvem, monkeypatch):
    # A checagem e sinal para humano; a analise e o trabalho. Perder o sinal
    # nao pode custar a analise — a publicadora cria a checagem no fim se ela
    # nao existir.
    _, _, lamb = nuvem

    def explodir(*a, **k):
        raise RuntimeError("api do github fora do ar")

    monkeypatch.setattr(buscador, "criar_em_progresso", explodir)

    buscador.lambda_handler(sqs(TRABALHO_PR), None)

    assert len(lamb.invocacoes) == 1
