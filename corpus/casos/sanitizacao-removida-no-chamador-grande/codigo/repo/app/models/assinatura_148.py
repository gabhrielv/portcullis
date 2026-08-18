from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_148:
    referencia: str
    descricao: str
    nome: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.nome})"
