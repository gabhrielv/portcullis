from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_104:
    codigo: str
    nome: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.codigo} ({self.rotulo})"
