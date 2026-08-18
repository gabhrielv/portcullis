from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_028:
    rotulo: str
    nome: str
    slug: str

    @property
    def resumo(self) -> str:
        return f"{self.rotulo} ({self.slug})"
