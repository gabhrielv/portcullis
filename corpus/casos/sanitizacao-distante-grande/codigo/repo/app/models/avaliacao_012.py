from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_012:
    referencia: str
    nome: str
    apelido: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.apelido})"
