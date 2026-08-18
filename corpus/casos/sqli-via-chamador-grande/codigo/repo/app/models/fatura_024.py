from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_024:
    referencia: str
    nome: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.descricao})"
