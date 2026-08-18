PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def resolver_entrega_005(texto: str) -> str:
    """Resolver o entrega_005 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_entrega_005(texto: str) -> str:
    """Normalizar o entrega_005 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_entrega_005(texto: str) -> str:
    """Sanitizar o entrega_005 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
