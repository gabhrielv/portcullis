from dataclasses import dataclass


@dataclass(frozen=True)
class Fornecedor_036:
    apelido: str
    nome: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.apelido} ({self.descricao})"
