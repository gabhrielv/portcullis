PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def validar_cliente_101(texto: str) -> str:
    """Validar o cliente_101 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_cliente_101(texto: str) -> str:
    """Normalizar o cliente_101 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_cliente_101(texto: str) -> str:
    """Limpar o cliente_101 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
