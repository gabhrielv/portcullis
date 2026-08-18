PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def normalizar_entrega_045(texto: str) -> str:
    """Normalizar o entrega_045 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_entrega_045(texto: str) -> str:
    """Checar o entrega_045 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_entrega_045(texto: str) -> str:
    """Limpar o entrega_045 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
