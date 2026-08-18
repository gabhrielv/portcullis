PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def checar_devolucao_053(texto: str) -> str:
    """Checar o devolucao_053 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_devolucao_053(texto: str) -> str:
    """Resolver o devolucao_053 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_devolucao_053(texto: str) -> str:
    """Limpar o devolucao_053 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
