import pytest
import requests
from dubles import ClienteFalso

from pra.llm.cliente import (
    ClienteLLM,
    CotaEsgotada,
    Ferramenta,
    ProvedorIndisponivel,
    RespostaLLM,
)
from pra.llm.groq import ESPERA_MAX_S, TENTATIVAS, ClienteGroq

FERRAMENTA = Ferramenta(nome="buscar", descricao="acha termos", parametros={})


class RespostaFalsa:
    def __init__(self, status, corpo=None, cabecalhos=None):
        self.status_code = status
        self._corpo = corpo if corpo is not None else {}
        self.headers = cabecalhos or {}

    def json(self):
        if self._corpo is None:
            raise ValueError("sem json")
        return self._corpo


def _corpo_com_chamada(argumentos='{"termos": ["valida_id"]}'):
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"function": {"name": "buscar", "arguments": argumentos}}
                    ],
                }
            }
        ],
        "usage": {"total_tokens": 812},
    }


def cliente():
    return ClienteGroq("chave", "modelo-x")


def _responder(monkeypatch, *respostas):
    """Devolve as respostas na ordem; repete a última se acabarem."""
    fila = list(respostas)
    chamadas = []

    def post(*args, **kwargs):
        chamadas.append(kwargs.get("json"))
        return fila.pop(0) if len(fila) > 1 else fila[0]

    monkeypatch.setattr("pra.llm.groq.requests.post", post)
    monkeypatch.setattr("pra.llm.groq.time.sleep", lambda _s: None)
    return chamadas


def test_dubles_satisfaz_o_protocolo():
    # Também prova que `import dubles` funciona a partir dos testes, que é do
    # que o agente inteiro vai depender a partir da T6.
    falso: ClienteLLM = ClienteFalso([RespostaLLM(texto="oi")])
    assert falso.conversar([], ()).texto == "oi"


def test_traduz_chamada_de_ferramenta(monkeypatch):
    _responder(monkeypatch, RespostaFalsa(200, _corpo_com_chamada()))
    resposta = cliente().conversar([], (FERRAMENTA,))
    assert resposta.chamadas[0].nome == "buscar"
    assert resposta.chamadas[0].argumentos == {"termos": ["valida_id"]}
    assert resposta.tokens == 812


def test_temperatura_zero_e_as_ferramentas_vao_no_corpo(monkeypatch):
    # Investigação não é criatividade: a mesma pergunta tem que dar a mesma
    # resposta, senão o corpus mede ruído em vez de medir o agente.
    chamadas = _responder(monkeypatch, RespostaFalsa(200, _corpo_com_chamada()))
    cliente().conversar([{"role": "user", "content": "oi"}], (FERRAMENTA,))
    corpo = chamadas[0]
    assert corpo["temperature"] == 0
    assert corpo["model"] == "modelo-x"
    assert corpo["tools"][0]["function"]["name"] == "buscar"


def test_argumento_malformado_nao_explode(monkeypatch):
    # Argumento que não parseia vira chamada sem argumento: a ferramenta
    # recusa, o loop segue e gasta um passo. Melhor que derrubar a análise.
    _responder(monkeypatch, RespostaFalsa(200, _corpo_com_chamada("{nao é json")))
    assert cliente().conversar([], (FERRAMENTA,)).chamadas[0].argumentos == {}


def test_resposta_so_com_texto(monkeypatch):
    corpo = {"choices": [{"message": {"content": "acho que sim"}}], "usage": {}}
    _responder(monkeypatch, RespostaFalsa(200, corpo))
    resposta = cliente().conversar([], (FERRAMENTA,))
    assert resposta.chamadas == ()
    assert resposta.texto == "acho que sim"


def test_429_de_cota_diaria_vira_cota_esgotada(monkeypatch):
    corpo = {"error": {"message": "Rate limit reached for model, limit per day"}}
    _responder(monkeypatch, RespostaFalsa(429, corpo))
    with pytest.raises(CotaEsgotada):
        cliente().conversar([], (FERRAMENTA,))


def test_429_por_minuto_tenta_de_novo_e_da_certo(monkeypatch):
    corpo429 = {"error": {"message": "Rate limit reached, limit per minute"}}
    _responder(
        monkeypatch,
        RespostaFalsa(429, corpo429),
        RespostaFalsa(200, _corpo_com_chamada()),
    )
    assert cliente().conversar([], (FERRAMENTA,)).tokens == 812


def test_retry_after_longo_demais_desiste_em_vez_de_dormir(monkeypatch):
    # A Lambda tem dez minutos no total. Dormir uma hora dentro dela é queimar
    # o orçamento inteiro para acordar e falhar do mesmo jeito.
    corpo429 = {"error": {"message": "Rate limit reached, limit per minute"}}
    _responder(
        monkeypatch,
        RespostaFalsa(429, corpo429, {"Retry-After": str(ESPERA_MAX_S + 1)}),
    )
    with pytest.raises(ProvedorIndisponivel, match="Retry-After"):
        cliente().conversar([], (FERRAMENTA,))


def test_erro_do_servidor_tenta_de_novo_e_desiste(monkeypatch):
    chamadas = _responder(monkeypatch, RespostaFalsa(503))
    with pytest.raises(ProvedorIndisponivel):
        cliente().conversar([], (FERRAMENTA,))
    assert len(chamadas) == TENTATIVAS


def test_chave_invalida_nao_fica_tentando(monkeypatch):
    # 401 não melhora com espera, e cada tentativa custa tempo de Lambda.
    chamadas = _responder(monkeypatch, RespostaFalsa(401, {"error": {"message": "bad key"}}))
    with pytest.raises(ProvedorIndisponivel):
        cliente().conversar([], (FERRAMENTA,))
    assert len(chamadas) == 1


def test_falha_de_rede_e_tratada_como_provedor_indisponivel(monkeypatch):
    chamadas = []

    def post(*args, **kwargs):
        chamadas.append(1)
        raise requests.ConnectionError("sem rota")

    monkeypatch.setattr("pra.llm.groq.requests.post", post)
    monkeypatch.setattr("pra.llm.groq.time.sleep", lambda _s: None)
    with pytest.raises(ProvedorIndisponivel):
        cliente().conversar([], (FERRAMENTA,))
    assert len(chamadas) == TENTATIVAS


def test_a_chave_nunca_aparece_na_mensagem_de_erro(monkeypatch):
    # A mensagem sobe até o evidencias.json, que vai para o S3 e para a
    # auditoria. Segredo não pode viajar junto.
    _responder(monkeypatch, RespostaFalsa(500, {"error": {"message": "erro chave"}}))
    with pytest.raises(ProvedorIndisponivel) as erro:
        ClienteGroq("segredo-secretissimo", "modelo-x").conversar([], (FERRAMENTA,))
    assert "segredo-secretissimo" not in str(erro.value)


def test_o_id_da_chamada_de_ferramenta_vem_do_provedor(monkeypatch):
    """Sem o id, o resultado não tem como voltar: `role: tool` exige um
    `tool_call_id` que case com o `tool_calls` do turno anterior."""
    corpo = _corpo_com_chamada()
    corpo["choices"][0]["message"]["tool_calls"][0]["id"] = "call_abc123"
    _responder(monkeypatch, RespostaFalsa(200, corpo))
    assert cliente().conversar([], (FERRAMENTA,)).chamadas[0].id == "call_abc123"


def test_provedor_sem_id_nao_derruba_a_traducao(monkeypatch):
    _responder(monkeypatch, RespostaFalsa(200, _corpo_com_chamada()))
    assert cliente().conversar([], (FERRAMENTA,)).chamadas[0].id == ""


def test_o_corpo_pede_amostragem_determinista(monkeypatch):
    """`temperature: 0` deixa a amostragem gulosa e não deixa o provedor
    determinístico — inferência em lote decide empate. O `seed` é best-effort
    documentado: não garante, reduz, e não substitui a repetição do corpus."""
    chamadas = _responder(monkeypatch, RespostaFalsa(200, _corpo_com_chamada()))
    cliente().conversar([], (FERRAMENTA,))
    assert chamadas[0]["temperature"] == 0
    assert chamadas[0]["seed"] == 0
