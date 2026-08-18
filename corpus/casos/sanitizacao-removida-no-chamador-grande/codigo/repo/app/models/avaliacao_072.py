from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_072:
    slug: str
    nome: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.slug} ({self.descricao})"
