from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_144:
    codigo: str
    slug: str
    referencia: str

    @property
    def resumo(self) -> str:
        return f"{self.codigo} ({self.referencia})"
