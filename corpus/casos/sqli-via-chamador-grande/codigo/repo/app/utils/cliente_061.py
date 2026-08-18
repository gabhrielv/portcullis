PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_cliente_061(texto: str) -> str:
    """Montar o cliente_061 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_cliente_061(texto: str) -> str:
    """Sanitizar o cliente_061 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_cliente_061(texto: str) -> str:
    """Checar o cliente_061 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
