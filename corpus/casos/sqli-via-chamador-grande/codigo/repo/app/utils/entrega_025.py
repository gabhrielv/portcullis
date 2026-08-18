PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def limpar_entrega_025(texto: str) -> str:
    """Limpar o entrega_025 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_entrega_025(texto: str) -> str:
    """Normalizar o entrega_025 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_entrega_025(texto: str) -> str:
    """Sanitizar o entrega_025 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
