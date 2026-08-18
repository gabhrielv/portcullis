from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_044:
    rotulo: str
    codigo: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.rotulo} ({self.descricao})"
