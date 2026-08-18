from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_000:
    descricao: str
    nome: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.rotulo})"
