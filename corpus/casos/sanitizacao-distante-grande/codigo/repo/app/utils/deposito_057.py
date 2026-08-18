PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_deposito_057(texto: str) -> str:
    """Sanitizar o deposito_057 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_deposito_057(texto: str) -> str:
    """Limpar o deposito_057 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_deposito_057(texto: str) -> str:
    """Montar o deposito_057 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
