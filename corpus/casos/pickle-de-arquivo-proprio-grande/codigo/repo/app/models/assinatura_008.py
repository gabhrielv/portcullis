from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_008:
    rotulo: str
    descricao: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.rotulo} ({self.codigo})"
