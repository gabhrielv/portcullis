from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_048:
    nome: str
    referencia: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.nome} ({self.codigo})"
