import hashlib
import hmac

from pra.webhook.assinatura import conferir_assinatura

SEGREDO = "segredo-de-teste"
CORPO = b'{"action":"opened"}'


def assinar(corpo: bytes, segredo: str) -> str:
    digest = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_assinatura_valida_passa():
    assert conferir_assinatura(CORPO, assinar(CORPO, SEGREDO), SEGREDO) is True


def test_assinatura_de_outro_segredo_falha():
    assert conferir_assinatura(CORPO, assinar(CORPO, "outro"), SEGREDO) is False


def test_corpo_alterado_falha():
    assinatura = assinar(CORPO, SEGREDO)
    assert conferir_assinatura(b'{"action":"closed"}', assinatura, SEGREDO) is False


def test_cabecalho_ausente_falha():
    assert conferir_assinatura(CORPO, None, SEGREDO) is False


def test_cabecalho_sem_prefixo_sha256_falha():
    digest = hmac.new(SEGREDO.encode(), CORPO, hashlib.sha256).hexdigest()
    assert conferir_assinatura(CORPO, digest, SEGREDO) is False


def test_cabecalho_com_lixo_falha_sem_explodir():
    assert conferir_assinatura(CORPO, "sha256=zzz", SEGREDO) is False


def test_assinatura_truncada_falha_sem_explodir():
    # compare_digest com strings de tamanhos diferentes não pode levantar.
    completa = assinar(CORPO, SEGREDO)
    assert conferir_assinatura(CORPO, completa[:20], SEGREDO) is False
