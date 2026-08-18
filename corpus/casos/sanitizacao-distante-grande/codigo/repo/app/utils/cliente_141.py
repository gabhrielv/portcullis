PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_cliente_141(texto: str) -> str:
    """Sanitizar o cliente_141 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_cliente_141(texto: str) -> str:
    """Validar o cliente_141 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_cliente_141(texto: str) -> str:
    """Normalizar o cliente_141 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
