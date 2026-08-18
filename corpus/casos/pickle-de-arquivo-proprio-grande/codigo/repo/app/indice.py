import pickle
from pathlib import Path

CACHE = Path("/var/cache/app/indice.pkl")


def gravar_indice(indice: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps(indice))


def carregar_indice() -> dict:
    """O arquivo e escrito por gravar_indice(), no mesmo servico.

    O diretorio nao e servido, nao recebe upload e nao e alcancavel por
    requisicao. O unico produtor deste arquivo esta tres linhas acima.
    """
    if not CACHE.exists():
        return {}
    return pickle.loads(CACHE.read_bytes())
