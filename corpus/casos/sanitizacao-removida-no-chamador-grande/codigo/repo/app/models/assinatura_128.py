from dataclasses import dataclass


@dataclass(frozen=True)
class Assinatura_128:
    rotulo: str
    apelido: str
    slug: str

    @property
    def resumo(self) -> str:
        return f"{self.rotulo} ({self.slug})"
