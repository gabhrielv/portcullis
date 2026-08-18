from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_084:
    referencia: str
    slug: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.codigo})"
