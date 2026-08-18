PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def validar_entrega_145(texto: str) -> str:
    """Validar o entrega_145 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_entrega_145(texto: str) -> str:
    """Resolver o entrega_145 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_entrega_145(texto: str) -> str:
    """Sanitizar o entrega_145 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
