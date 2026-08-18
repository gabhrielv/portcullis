from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_136:
    slug: str
    rotulo: str
    nome: str

    @property
    def resumo(self) -> str:
        return f"{self.slug} ({self.nome})"
