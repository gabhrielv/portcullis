from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_080:
    descricao: str
    codigo: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.rotulo})"
