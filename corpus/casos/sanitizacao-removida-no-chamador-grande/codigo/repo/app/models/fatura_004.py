from dataclasses import dataclass


@dataclass(frozen=True)
class Fatura_004:
    apelido: str
    descricao: str
    rotulo: str

    @property
    def resumo(self) -> str:
        return f"{self.apelido} ({self.rotulo})"
