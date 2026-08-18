PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def validar_deposito_037(texto: str) -> str:
    """Validar o deposito_037 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_deposito_037(texto: str) -> str:
    """Resolver o deposito_037 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_deposito_037(texto: str) -> str:
    """Sanitizar o deposito_037 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
