from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_124:
    nome: str
    slug: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.nome} ({self.descricao})"
