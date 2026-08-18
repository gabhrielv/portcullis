from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_032:
    slug: str
    referencia: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.slug} ({self.codigo})"
