PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def limpar_devolucao_073(texto: str) -> str:
    """Limpar o devolucao_073 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_devolucao_073(texto: str) -> str:
    """Resolver o devolucao_073 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_devolucao_073(texto: str) -> str:
    """Checar o devolucao_073 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
