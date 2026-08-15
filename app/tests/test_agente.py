from pathlib import Path

from dubles import ClienteFalso, ClienteQueFalha

from portcullis.agente.ferramentas import Caixa
from portcullis.agente.loop import PASSOS_MAX, investigar
from portcullis.llm.cliente import Chamada, CotaEsgotada, RespostaLLM
from portcullis.modelos import Achado, Resposta, Severidade

ARQUIVO = "app/db.py"


def achado():
    return Achado(
        regra="python.lang.security.audit.sqli",
        severidade=Severidade.ERRO,
        caminho=ARQUIVO,
        linha_inicio=2,
        linha_fim=2,
        mensagem="possível SQL injection",
        categoria="security",
    )


def caixa(tmp_path: Path) -> Caixa:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "db.py").write_text(
        "def por_id(identificador):\n    return 'SELECT * WHERE id = ' + identificador\n"
    )
    return Caixa(tmp_path)


def concluir(entrada="nao", sanitizacao="nao_sei", prova=None):
    return RespostaLLM(
        chamadas=(
            Chamada(
                nome="concluir",
                argumentos={
                    "entrada_controlavel": entrada,
                    "sanitizacao_encontrada": sanitizacao,
                    "prova": prova,
                    "raciocinio": "olhei os chamadores",
                },
            ),
        ),
        tokens=100,
    )


def test_conclusao_no_primeiro_passo(tmp_path):
    cliente = ClienteFalso([concluir(entrada="nao")])
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.entrada_controlavel is Resposta.NAO
    assert e.passos == 1


def test_usa_ferramenta_e_depois_conclui(tmp_path):
    cliente = ClienteFalso(
        [
            RespostaLLM(
                chamadas=(Chamada(nome="buscar", argumentos={"termos": ["por_id"]}),),
                tokens=50,
            ),
            concluir(entrada="sim"),
        ]
    )
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.entrada_controlavel is Resposta.SIM
    assert e.passos == 2
    assert e.tokens == 150


def test_estourar_o_orcamento_vira_nao_sei(tmp_path):
    """Um loop sem orçamento não é um loop, é um vazamento (§3)."""
    infinito = [
        RespostaLLM(chamadas=(Chamada(nome="buscar", argumentos={"termos": ["x"]}),))
        for _ in range(PASSOS_MAX + 5)
    ]
    e = investigar(achado(), caixa(tmp_path), ClienteFalso(infinito))
    assert e.entrada_controlavel is Resposta.NAO_SEI
    assert e.sanitizacao_encontrada is Resposta.NAO_SEI
    assert e.passos == PASSOS_MAX


def test_prova_inexistente_e_marcada_invalida(tmp_path):
    cliente = ClienteFalso([concluir(sanitizacao="sim", prova="app/inventado.py:99")])
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.prova == "app/inventado.py:99"
    assert e.prova_valida is False


def test_prova_existente_e_marcada_valida(tmp_path):
    cliente = ClienteFalso([concluir(sanitizacao="sim", prova="app/db.py:1")])
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.prova_valida is True


def test_resposta_fora_do_vocabulario_vira_nao_sei(tmp_path):
    """O modelo escreve o valor; o vocabulário é nosso. Qualquer coisa fora
    dele bloqueia, nunca libera."""
    cliente = ClienteFalso([concluir(entrada="provavelmente nao")])
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.entrada_controlavel is Resposta.NAO_SEI


def test_ferramenta_inexistente_e_recusada_e_o_loop_segue(tmp_path):
    cliente = ClienteFalso(
        [
            RespostaLLM(chamadas=(Chamada(nome="rodar_shell", argumentos={}),)),
            concluir(entrada="nao"),
        ]
    )
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.entrada_controlavel is Resposta.NAO
    assert e.passos == 2


def test_resposta_sem_chamada_nenhuma_vira_nao_sei(tmp_path):
    """Texto solto não é evidência. O loop empurra de volta para o formato, e
    quando o orçamento acaba a resposta é nao_sei — que bloqueia."""
    cliente = ClienteFalso([RespostaLLM(texto="acho que está tudo bem")] * PASSOS_MAX)
    e = investigar(achado(), caixa(tmp_path), cliente)
    assert e.entrada_controlavel is Resposta.NAO_SEI
    assert e.passos == PASSOS_MAX


def test_cota_esgotada_sobe_para_quem_chamou(tmp_path):
    """A investigadora precisa saber que degradou. Engolir aqui esconderia."""
    cliente = ClienteQueFalha(CotaEsgotada("acabou"))
    try:
        investigar(achado(), caixa(tmp_path), cliente)
    except CotaEsgotada:
        return
    raise AssertionError("CotaEsgotada deveria ter subido")


def test_a_janela_do_achado_entra_no_primeiro_prompt(tmp_path):
    cliente = ClienteFalso([concluir()])
    investigar(achado(), caixa(tmp_path), cliente)
    primeira = cliente.conversas[0]
    assert any("por_id" in str(m.get("content", "")) for m in primeira)
