from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_068:
    descricao: str
    nome: str
    referencia: str

    @property
    def resumo(self) -> str:
        return f"{self.descricao} ({self.referencia})"
