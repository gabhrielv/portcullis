from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_052:
    descricao: str
    referencia: str
    slug: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.slug})"
