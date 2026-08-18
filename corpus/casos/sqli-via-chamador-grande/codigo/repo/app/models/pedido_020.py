from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_020:
    apelido: str
    nome: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.apelido} ({self.codigo})"
