from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_060:
    descricao: str
    apelido: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.rotulo})"
