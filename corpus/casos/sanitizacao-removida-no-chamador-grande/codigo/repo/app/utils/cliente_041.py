PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_cliente_041(texto: str) -> str:
    """Montar o cliente_041 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_cliente_041(texto: str) -> str:
    """Normalizar o cliente_041 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_cliente_041(texto: str) -> str:
    """Validar o cliente_041 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
