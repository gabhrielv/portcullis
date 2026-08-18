from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_016:
    apelido: str
    rotulo: str
    referencia: str

    @property
    def resumo(self) -> str:
        return f"{self.apelido} ({self.referencia})"
