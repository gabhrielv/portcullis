"""Contratos compartilhados por todos os componentes.

Nada aqui importa boto3, requests ou qualquer coisa de AWS/GitHub: o analisador
roda no container e não pode ter dependência de nuvem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severidade(Enum):
    """Vocabulário do próprio Semgrep, sem tradução."""

    ERRO = "ERROR"
    AVISO = "WARNING"
    INFO = "INFO"


class Evento(Enum):
    PULL_REQUEST = "pull_request"
    PUSH = "push"


class EstadoVeredito(Enum):
    LIBERADO = "liberado"
    BLOQUEADO = "bloqueado"
    NAO_CONCLUI = "nao_conclui"


@dataclass(frozen=True)
class FaixaLinhas:
    inicio: int
    fim: int

    def intersecta(self, inicio: int, fim: int) -> bool:
        return inicio <= self.fim and fim >= self.inicio


@dataclass(frozen=True)
class Achado:
    """`categoria` é o `metadata.category` do semgrep: security, performance,
    correctness. Vem `None` quando a regra não declara."""

    regra: str
    severidade: Severidade
    caminho: str
    linha_inicio: int
    linha_fim: int
    mensagem: str
    categoria: str | None = None


class Resposta(Enum):
    """As três respostas que o agente pode dar. `NAO_SEI` bloqueia — ver D6."""

    SIM = "sim"
    NAO = "nao"
    NAO_SEI = "nao_sei"


def chave_do_achado(achado: Achado) -> str:
    """Casa achado com evidência.

    Índice de lista quebraria em silêncio se qualquer coisa reordenasse; isto é
    derivado do próprio achado, e a mesma função gera dos dois lados.
    """
    return f"{achado.regra}|{achado.caminho}|{achado.linha_inicio}|{achado.linha_fim}"


@dataclass(frozen=True)
class Evidencia:
    """O que o agente devolve. Ele NUNCA emite veredito — ver D6.

    `prova_valida` é calculado por nós, conferindo que o `arquivo:linha` existe
    no pacote: o modelo declara a prova, quem verifica é o código.
    """

    chave: str
    entrada_controlavel: Resposta
    sanitizacao_encontrada: Resposta
    prova: str | None = None
    prova_valida: bool = False
    raciocinio: str = ""
    passos: int = 0
    tokens: int = 0


@dataclass(frozen=True)
class Contexto:
    """O que a buscadora sabe e o analisador precisa.

    `tudo_novo` liga o modo conservador: quando não dá para calcular o diff,
    todo achado conta como novo.
    """

    owner: str
    repo: str
    head_sha: str
    evento: Evento
    linhas_tocadas: dict[str, tuple[FaixaLinhas, ...]] = field(default_factory=dict)
    numero_pr: int | None = None
    base_sha: str | None = None
    tudo_novo: bool = False

    @property
    def id_analise(self) -> str:
        return f"{self.owner}/{self.repo}@{self.head_sha}"


@dataclass(frozen=True)
class Veredito:
    """Resultado da regra determinística.

    bloqueantes   -> achado novo com severidade bloqueante; anotação `failure`.
    avisos        -> achado novo de severidade menor; não trava.
    preexistentes -> achado em linha que o PR não tocou; só no resumo.
    silenciados   -> achado novo que bateu numa exceção declarada; só no resumo.
    silenciados_por_evidencia -> achado que bloquearia, silenciado pelo agente.
    """

    estado: EstadoVeredito
    bloqueantes: tuple[Achado, ...]
    avisos: tuple[Achado, ...]
    preexistentes: tuple[Achado, ...]
    versao_regra: str
    silenciados: tuple[Achado, ...] = ()
    # Separado de `silenciados` de propósito: aquele é exceção que uma PESSOA
    # escreveu em excecoes.py, este é julgamento de MODELO. Num campo só, a
    # auditoria perderia a diferença entre decisão humana e decisão de máquina
    # — que é exatamente a pergunta que a D11 existe para responder.
    silenciados_por_evidencia: tuple[Achado, ...] = ()
    degradado: bool = False
    motivo: str | None = None
