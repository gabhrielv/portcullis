from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_140:
    referencia: str
    rotulo: str
    nome: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.nome})"
