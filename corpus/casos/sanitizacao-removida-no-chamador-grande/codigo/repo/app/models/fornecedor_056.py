from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_056:
    referencia: str
    slug: str
    apelido: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.apelido})"
