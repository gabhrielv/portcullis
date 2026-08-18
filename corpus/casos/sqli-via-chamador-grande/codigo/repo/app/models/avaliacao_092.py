from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_092:
    nome: str
    rotulo: str
    referencia: str

    @property
    def resumo(self) -> str:
        return f"{self.nome} ({self.referencia})"
