from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_088:
    referencia: str
    descricao: str
    codigo: str

    @property
    def resumo(self) -> str:
        return f"{self.referencia} ({self.codigo})"
