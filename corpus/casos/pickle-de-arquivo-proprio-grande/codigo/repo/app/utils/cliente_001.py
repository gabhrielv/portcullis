PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def normalizar_cliente_001(texto: str) -> str:
    """Normalizar o cliente_001 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_cliente_001(texto: str) -> str:
    """Limpar o cliente_001 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_cliente_001(texto: str) -> str:
    """Montar o cliente_001 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
