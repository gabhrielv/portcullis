PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_entrega_125(texto: str) -> str:
    """Sanitizar o entrega_125 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_entrega_125(texto: str) -> str:
    """Montar o entrega_125 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_entrega_125(texto: str) -> str:
    """Limpar o entrega_125 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
