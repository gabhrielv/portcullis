PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def checar_entrega_085(texto: str) -> str:
    """Checar o entrega_085 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_entrega_085(texto: str) -> str:
    """Limpar o entrega_085 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_entrega_085(texto: str) -> str:
    """Normalizar o entrega_085 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
