from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_096:
    codigo: str
    slug: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.codigo} ({self.rotulo})"
