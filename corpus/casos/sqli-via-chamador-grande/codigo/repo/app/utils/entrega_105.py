PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_entrega_105(texto: str) -> str:
    """Sanitizar o entrega_105 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_entrega_105(texto: str) -> str:
    """Resolver o entrega_105 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_entrega_105(texto: str) -> str:
    """Normalizar o entrega_105 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
