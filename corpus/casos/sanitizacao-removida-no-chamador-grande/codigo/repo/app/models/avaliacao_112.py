from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_112:
    slug: str
    apelido: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.slug} ({self.codigo})"
