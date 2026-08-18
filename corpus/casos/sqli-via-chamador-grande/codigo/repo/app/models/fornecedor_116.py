from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_116:
    referencia: str
    codigo: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.rotulo})"
