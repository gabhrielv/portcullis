from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_064:
    nome: str
    rotulo: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.nome} ({self.codigo})"
