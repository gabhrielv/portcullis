PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def normalizar_entrega_065(texto: str) -> str:
    """Normalizar o entrega_065 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_entrega_065(texto: str) -> str:
    """Montar o entrega_065 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_entrega_065(texto: str) -> str:
    """Limpar o entrega_065 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
