from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_076:
    nome: str
    referencia: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.nome} ({self.descricao})"
