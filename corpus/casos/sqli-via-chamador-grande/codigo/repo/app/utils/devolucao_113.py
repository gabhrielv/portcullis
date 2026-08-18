PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def validar_devolucao_113(texto: str) -> str:
    """Validar o devolucao_113 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_devolucao_113(texto: str) -> str:
    """Checar o devolucao_113 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_devolucao_113(texto: str) -> str:
    """Resolver o devolucao_113 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
