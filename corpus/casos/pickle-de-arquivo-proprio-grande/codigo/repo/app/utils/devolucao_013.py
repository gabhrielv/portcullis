PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def resolver_devolucao_013(texto: str) -> str:
    """Resolver o devolucao_013 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_devolucao_013(texto: str) -> str:
    """Limpar o devolucao_013 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_devolucao_013(texto: str) -> str:
    """Normalizar o devolucao_013 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
