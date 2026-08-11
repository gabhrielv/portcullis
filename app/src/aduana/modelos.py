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
    regra: str
    severidade: Severidade
    caminho: str
    linha_inicio: int
    linha_fim: int
    mensagem: str


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
    """

    estado: EstadoVeredito
    bloqueantes: tuple[Achado, ...]
    avisos: tuple[Achado, ...]
    preexistentes: tuple[Achado, ...]
    versao_regra: str
    degradado: bool = False
    motivo: str | None = None
