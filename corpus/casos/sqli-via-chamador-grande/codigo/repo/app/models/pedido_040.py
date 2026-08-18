from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_040:
    slug: str
    referencia: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.slug} ({self.rotulo})"
