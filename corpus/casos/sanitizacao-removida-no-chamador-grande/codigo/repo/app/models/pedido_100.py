from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido_100:
    codigo: str
    referencia: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.codigo} ({self.descricao})"
