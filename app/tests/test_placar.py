"""A pontuação do corpus. Ela é o critério de aceite de qualquer mexida no
prompt ou no modelo — errar aqui reporta um número bonito sem avisar."""

import json

import rodar
from placar import (
    FRACAO_RUIDO,
    aceite,
    evidencia_bate,
    linha_de_base,
    mede,
    render,
    resumir,
    ruido_minimo,
    ruido_removido,
)

from portcullis.modelos import Evidencia, Resposta


def evidencia(entrada="nao_sei", sanitizacao="nao_sei", prova=None, prova_valida=False):
    return Evidencia(
        chave="k",
        entrada_controlavel=Resposta(entrada),
        sanitizacao_encontrada=Resposta(sanitizacao),
        prova=prova,
        prova_valida=prova_valida,
        raciocinio="porque sim",
        passos=3,
        tokens=900,
    )


def test_campo_ausente_na_esperada_nao_e_conferido():
    """`{entrada_controlavel: sim}` aceita qualquer sanitizacao: o caso só tem
    opinião sobre a origem do valor."""
    aceitas = [{"entrada_controlavel": "sim"}]
    assert evidencia_bate(evidencia(entrada="sim", sanitizacao="nao"), aceitas)
    assert evidencia_bate(evidencia(entrada="sim", sanitizacao="sim"), aceitas)


def test_campo_presente_na_esperada_precisa_bater():
    aceitas = [{"entrada_controlavel": "sim", "sanitizacao_encontrada": "nao"}]
    assert not evidencia_bate(evidencia(entrada="sim", sanitizacao="sim"), aceitas)


def test_qualquer_uma_da_lista_basta():
    """`markup-com-inteiro` tem duas leituras honestas."""
    aceitas = [
        {"entrada_controlavel": "nao"},
        {"entrada_controlavel": "sim", "sanitizacao_encontrada": "sim", "prova_em": "app/x.py"},
    ]
    assert evidencia_bate(evidencia(entrada="nao"), aceitas)
    assert evidencia_bate(
        evidencia(entrada="sim", sanitizacao="sim", prova="app/x.py:4", prova_valida=True),
        aceitas,
    )


def test_prova_em_compara_o_arquivo_e_exige_prova_valida():
    aceitas = [{"sanitizacao_encontrada": "sim", "prova_em": "app/middleware.py"}]
    boa = evidencia(sanitizacao="sim", prova="app/middleware.py:7", prova_valida=True)
    outro_arquivo = evidencia(sanitizacao="sim", prova="app/outro.py:7", prova_valida=True)
    sem_conferir = evidencia(sanitizacao="sim", prova="app/middleware.py:7")
    assert evidencia_bate(boa, aceitas)
    assert not evidencia_bate(outro_arquivo, aceitas)
    assert not evidencia_bate(sem_conferir, aceitas)


def test_so_falso_positivo_e_armadilha_medem():
    """Nos vulneráveis comuns o portão já bloqueia por padrão: repetir custa
    cota e não mede nada."""
    assert mede({"gabarito": "FALSO_POSITIVO"})
    assert mede({"gabarito": "VULNERAVEL", "arma_falso_negativo": True})
    assert not mede({"gabarito": "VULNERAVEL"})


def _caso(gabarito="VULNERAVEL", **extra):
    return {"id": "x", "dificuldade": "media", "gabarito": gabarito, **extra}


def _exec(silenciou, bateu=True):
    return {"silenciou": silenciou, "raciocinio_bateu": bateu, "passos": 3, "tokens": 900}


def test_acertar_em_todas_as_execucoes_conta_como_acerto():
    linha = resumir(_caso(), [_exec(False), _exec(False)])
    assert linha["veredito_certo"] is True
    assert linha["estavel"] is True


def test_uma_execucao_errada_derruba_o_caso():
    """Média esconde: um portão que solta em 1 de 3 rodadas solta."""
    linha = resumir(_caso(), [_exec(False), _exec(True), _exec(False)])
    assert linha["veredito_certo"] is False
    assert linha["falso_negativo"] is True
    assert linha["estavel"] is False


def test_silenciar_falso_positivo_nao_e_falso_negativo():
    linha = resumir(_caso("FALSO_POSITIVO"), [_exec(True)])
    assert linha["veredito_certo"] is True
    assert linha["falso_negativo"] is False


def test_veredito_certo_com_raciocinio_errado_fica_registrado():
    """Bloqueou porque desistiu conta como veredito certo e raciocínio errado —
    é a distância entre as duas colunas que diz quanto do placar é sorte."""
    linha = resumir(_caso(), [_exec(False, bateu=False)])
    assert linha["veredito_certo"] is True
    assert linha["raciocinio_certo"] is False


def test_linha_de_base_e_o_agente_que_nao_silencia_nada():
    entradas = [
        _caso("VULNERAVEL"),
        _caso("VULNERAVEL", arma_falso_negativo=True),
        _caso("FALSO_POSITIVO"),
    ]
    base = linha_de_base(entradas)
    assert base["veredito"] == 2
    assert base["raciocinio"] == 0
    assert base["falso_negativos"] == 0
    assert base["ruido_removido"] == 0


def test_a_base_conta_o_caso_em_que_nao_sei_e_a_resposta_certa():
    """A base é derivada, não cravada. Se um gabarito passar a aceitar
    `nao_sei`, o agente nulo ganha aquele ponto — e a coluna `base` precisa
    dizer isso, senão o placar credita ao agente um acerto que era de graça."""
    entradas = [
        _caso("VULNERAVEL", evidencia_aceita=[{"entrada_controlavel": "sim"}]),
        _caso("VULNERAVEL", evidencia_aceita=[{"entrada_controlavel": "nao_sei"}]),
    ]
    assert linha_de_base(entradas)["raciocinio"] == 1


def test_falso_negativo_em_caso_obvio_entra_no_indice_do_corpus_todo():
    """Silenciar um vulnerável sem armadilha não move o índice das armadilhas.
    Se não houvesse a linha do corpus todo, o pior erro possível apareceria só
    como item de lista."""
    entradas = [
        _caso("VULNERAVEL", arma_falso_negativo=True),
        _caso("VULNERAVEL"),
    ]
    # silenciou o óbvio, acertou a armadilha
    linhas = [resumir(entradas[0], [_exec(False)]), resumir(entradas[1], [_exec(True)])]
    texto = " ".join(" ".join(x.split()) for x in render(linhas, entradas).splitlines())
    assert "falso-negativos 0/1" in texto
    assert "no corpus todo 1/2" in texto


def test_o_placar_mostra_a_coluna_da_linha_de_base():
    """Sem ela, `2/3` parece bom e esconde que o agente nulo já tirava 2."""
    entradas = [_caso("VULNERAVEL"), _caso("VULNERAVEL"), _caso("FALSO_POSITIVO")]
    linhas = [resumir(e, [_exec(e["gabarito"] == "FALSO_POSITIVO")]) for e in entradas]
    linhas_do_texto = [" ".join(x.split()) for x in render(linhas, entradas).splitlines()]
    assert "medido base" in linhas_do_texto
    assert "veredito 3/3 2/3" in linhas_do_texto
    assert any(x.startswith("raciocínio 3/3 0/3") for x in linhas_do_texto)


# --- o aceite ---------------------------------------------------------------


def _corpus(vulneraveis: int, positivos: int):
    """Devolve (entradas, construtor de linhas) para montar um placar de teste."""
    entradas = [_caso("VULNERAVEL") for _ in range(vulneraveis)]
    entradas += [_caso("FALSO_POSITIVO") for _ in range(positivos)]
    return entradas


def _linhas(entradas, silenciados_vuln=0, silenciados_fp=None):
    """`silenciados_fp` é quantos falso-positivos o agente acertou (silenciou)."""
    if silenciados_fp is None:
        silenciados_fp = sum(1 for e in entradas if e["gabarito"] == "FALSO_POSITIVO")
    linhas, vistos_v, vistos_f = [], 0, 0
    for e in entradas:
        if e["gabarito"] == "VULNERAVEL":
            silenciou = vistos_v < silenciados_vuln
            vistos_v += 1
        else:
            silenciou = vistos_f < silenciados_fp
            vistos_f += 1
        linhas.append(resumir(e, [_exec(silenciou)]))
    return linhas


def test_agente_perfeito_passa():
    entradas = _corpus(15, 7)
    passou, reprovou = aceite(_linhas(entradas), entradas)
    assert passou is True
    assert reprovou == []


def test_um_falso_negativo_reprova_mesmo_com_ruido_perfeito():
    """A regra que não se compensa: 21/22 de veredito com uma vulnerabilidade
    solta não passa."""
    entradas = _corpus(15, 7)
    passou, reprovou = aceite(_linhas(entradas, silenciados_vuln=1), entradas)
    assert passou is False
    assert any("falso-negativos" in m for m in reprovou)


def test_ruido_abaixo_do_minimo_reprova():
    entradas = _corpus(15, 7)
    linhas = _linhas(entradas, silenciados_fp=ruido_minimo(entradas) - 1)
    passou, reprovou = aceite(linhas, entradas)
    assert passou is False
    assert any("ruído removido" in m for m in reprovou)


def test_o_piso_e_ancorado_no_agente_nulo_nao_num_numero_fixo():
    """`>= 19` apodreceria na próxima mudança de tamanho do corpus — foi o que
    aconteceu com o `> 12/20`. O piso acompanha a base."""
    pequeno = _corpus(5, 3)
    grande = _corpus(15, 7)
    piso_pequeno = linha_de_base(pequeno)["veredito"] + ruido_minimo(pequeno)
    piso_grande = linha_de_base(grande)["veredito"] + ruido_minimo(grande)
    assert piso_pequeno == 5 + ruido_minimo(pequeno)
    assert piso_grande == 15 + ruido_minimo(grande)


def test_o_piso_e_redundante_enquanto_os_outros_dois_valerem():
    """A rede, e o alarme.

    Para caso vulnerável `veredito_certo` é o mesmo que `not falso_negativo`,
    então zero falso-negativo mais o mínimo de ruído já colocam o veredito
    acima do piso. Enquanto isso valer, o piso nunca reprova sozinho.

    Se este teste quebrar, alguém afrouxou o critério de falso-negativo e o
    piso passou a ser o que segura o portão — que é a hora de olhar para ele,
    e não a hora de apagá-lo.
    """
    entradas = _corpus(15, 7)
    for ruido in range(ruido_minimo(entradas), 8):
        linhas = _linhas(entradas, silenciados_vuln=0, silenciados_fp=ruido)
        passou, reprovou = aceite(linhas, entradas)
        assert passou is True, reprovou
        assert not any("veredito:" in m for m in reprovou)


def test_o_placar_imprime_o_veredito_do_aceite():
    """Sem isto o aceite volta a depender de alguém somar as colunas a olho."""
    entradas = _corpus(15, 7)
    aprovado = render(_linhas(entradas), entradas)
    reprovado = render(_linhas(entradas, silenciados_vuln=1), entradas)
    assert "APROVADO" in aprovado
    assert "REPROVADO" in reprovado


def test_calar_pelo_motivo_errado_nao_conta_como_ruido_removido():
    """O buraco que o ARQUITETURA nomeia: em `sqli-constante` o modelo pode
    calar apontando uma "sanitização" no arquivo do enum — ela existe, passa no
    `prova_valida`, e não sanitiza nada. Contando só o veredito, esse acerto
    pagaria igual ao de quem entendeu."""
    entradas = [_caso("FALSO_POSITIVO"), _caso("FALSO_POSITIVO")]
    linhas = [
        resumir(entradas[0], [_exec(True, bateu=True)]),   # calou, e entendeu
        resumir(entradas[1], [_exec(True, bateu=False)]),  # calou pelo motivo errado
    ]
    assert ruido_removido(linhas) == 1


def test_o_minimo_de_ruido_acompanha_o_tamanho_do_corpus():
    """`>= 4` fixo viraria trivial num corpus com 20 falso-positivos: estaria
    dizendo que remover um quinto do ruído justifica o marco inteiro."""
    assert ruido_minimo(_corpus(15, 7)) == 4      # o corpus de hoje, número idêntico
    assert ruido_minimo(_corpus(15, 20)) == 11
    assert ruido_minimo(_corpus(15, 4)) == 3      # e não exige perfeição no pequeno
    assert 0 < FRACAO_RUIDO < 1


def test_agente_que_cala_tudo_pelo_motivo_errado_reprova():
    """Veredito bom, raciocínio vazio: reprova no ruído, que agora exige os dois."""
    entradas = _corpus(15, 7)
    linhas = [
        resumir(e, [_exec(e["gabarito"] == "FALSO_POSITIVO", bateu=False)]) for e in entradas
    ]
    passou, reprovou = aceite(linhas, entradas)
    assert passou is False
    assert any("motivo certo" in m for m in reprovou)


# --- retomada do aceite ------------------------------------------------------
#
# O aceite da D28 custa mais tokens que o teto diário do provedor permite, então
# ele precisa caber em duas sentadas. O risco de juntar é medir uma coisa e
# reportar outra: por isso o casamento é exato nos três eixos.

def _placar(tmp_path, nome, *, versao, modelo, repeticoes, ids):
    destino = tmp_path / nome
    destino.write_text(
        json.dumps(
            {
                "versao_prompt": versao,
                "modelo": modelo,
                "repeticoes": repeticoes,
                "linhas": [{"id": i} for i in ids],
            }
        )
    )
    return destino


def test_retomada_reaproveita_a_mesma_configuracao(tmp_path, monkeypatch):
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    _placar(tmp_path, "a.json", versao=rodar.VERSAO_PROMPT, modelo="m", repeticoes=3,
            ids=["sqli-direto", "morto-mas-novo"])

    assert set(rodar.medidos_antes("m", 3)) == {"sqli-direto", "morto-mas-novo"}


def test_retomada_ignora_versao_de_prompt_diferente(tmp_path, monkeypatch):
    """Prompt diferente é agente diferente. Juntar produziria um placar que não
    corresponde a nenhuma das duas versões."""
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    _placar(tmp_path, "a.json", versao="0", modelo="m", repeticoes=3, ids=["sqli-direto"])

    assert rodar.medidos_antes("m", 3) == {}


def test_retomada_ignora_modelo_diferente(tmp_path, monkeypatch):
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    _placar(tmp_path, "a.json", versao=rodar.VERSAO_PROMPT, modelo="outro",
            repeticoes=3, ids=["sqli-direto"])

    assert rodar.medidos_antes("m", 3) == {}


def test_retomada_ignora_numero_de_repeticoes_diferente(tmp_path, monkeypatch):
    """Metade medida 1x e metade 3x não é um aceite com 3."""
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    _placar(tmp_path, "a.json", versao=rodar.VERSAO_PROMPT, modelo="m", repeticoes=1,
            ids=["sqli-direto"])

    assert rodar.medidos_antes("m", 3) == {}


def test_retomada_deixa_o_arquivo_mais_recente_vencer(tmp_path, monkeypatch):
    """Remedir um caso tem de valer sobre a medição antiga dele."""
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    for nome, marca in (("5-m-20260101-000000.json", "velho"),
                        ("5-m-20260102-000000.json", "novo")):
        (tmp_path / nome).write_text(
            json.dumps({"versao_prompt": rodar.VERSAO_PROMPT, "modelo": "m",
                        "repeticoes": 3,
                        "linhas": [{"id": "sqli-direto", "marca": marca}]})
        )

    assert rodar.medidos_antes("m", 3)["sqli-direto"]["marca"] == "novo"


def test_retomada_ignora_placar_corrompido(tmp_path, monkeypatch):
    """Arquivo truncado por execução morta no meio não pode derrubar a retomada."""
    monkeypatch.setattr(rodar, "PLACARES", tmp_path)
    (tmp_path / "quebrado.json").write_text("{ nao e json")
    _placar(tmp_path, "b.json", versao=rodar.VERSAO_PROMPT, modelo="m", repeticoes=3,
            ids=["sqli-direto"])

    assert set(rodar.medidos_antes("m", 3)) == {"sqli-direto"}


# --- contaminacao da medicao -------------------------------------------------


class _ClienteQueRecusa:
    """Recusa `n` vezes e depois responde. Reproduz o 429 de teto por minuto
    que o `sanitizacao-distante-grande` levou em 21/08/2026."""

    modelo = "m"

    def __init__(self, recusas):
        self.restam = recusas
        self.chamadas = 0

    def conversar(self, mensagens, ferramentas):
        from portcullis.llm.cliente import ProvedorIndisponivel

        self.chamadas += 1
        if self.restam > 0:
            self.restam -= 1
            raise ProvedorIndisponivel("429: teto por minuto")
        from portcullis.llm.cliente import Chamada, RespostaLLM

        return RespostaLLM(
            chamadas=(
                Chamada(
                    nome="concluir",
                    id="c",
                    argumentos={
                        "entrada_controlavel": "nao",
                        "sanitizacao_encontrada": "nao",
                        "raciocinio": "investiguei",
                    },
                ),
            ),
            tokens=10,
        )


def _achado_qualquer():
    from portcullis.modelos import Achado, Severidade

    return Achado("r", Severidade.ERRO, "app/db.py", 1, 1, "m")


def test_recusa_do_provedor_e_repetida_em_vez_de_pontuada(tmp_path):
    """Recusa nao e' medicao. Pontua-la como `nao_sei` faria a falha de
    infraestrutura contar como erro do agente — e como o aceite exige
    unanimidade, UMA execucao contaminada reprovaria o caso inteiro."""
    from portcullis.agente.ferramentas import Caixa

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "db.py").write_text("x = 1\n")
    cliente = _ClienteQueRecusa(recusas=2)

    saida = rodar._uma_execucao(
        {"evidencia_aceita": []}, _achado_qualquer(), Caixa(tmp_path), cliente
    )
    assert saida["entrada_controlavel"] == "nao", "devia ter repetido ate' responder"


def test_recusa_em_todas_as_tentativas_deixa_o_caso_por_medir(tmp_path):
    """Sem isso, o caso seria bancado com um resultado que nunca foi medido —
    e a retomada nunca voltaria nele."""
    import pytest

    from portcullis.agente.ferramentas import Caixa

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "db.py").write_text("x = 1\n")
    cliente = _ClienteQueRecusa(recusas=99)

    with pytest.raises(rodar.MedicaoContaminada):
        rodar._uma_execucao(
            {"evidencia_aceita": []}, _achado_qualquer(), Caixa(tmp_path), cliente
        )
