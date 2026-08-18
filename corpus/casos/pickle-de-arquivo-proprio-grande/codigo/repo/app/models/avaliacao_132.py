from dataclasses import dataclass


@dataclass(frozen=True)
class Avaliacao_132:
    apelido: str
    codigo: str
    descricao: str

    @property
    def resumo(self) -> str:
        return f"{self.apelido} ({self.descricao})"
