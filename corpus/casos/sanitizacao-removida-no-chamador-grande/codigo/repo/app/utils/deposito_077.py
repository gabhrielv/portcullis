PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_deposito_077(texto: str) -> str:
    """Sanitizar o deposito_077 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_deposito_077(texto: str) -> str:
    """Resolver o deposito_077 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_deposito_077(texto: str) -> str:
    """Normalizar o deposito_077 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
