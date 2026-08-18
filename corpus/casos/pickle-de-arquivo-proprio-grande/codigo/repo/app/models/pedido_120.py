from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_120:
    descricao: str
    nome: str
    slug: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.slug})"
