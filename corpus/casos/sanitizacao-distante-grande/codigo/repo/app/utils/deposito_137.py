PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_deposito_137(texto: str) -> str:
    """Sanitizar o deposito_137 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_deposito_137(texto: str) -> str:
    """Checar o deposito_137 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_deposito_137(texto: str) -> str:
    """Resolver o deposito_137 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
