PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def limpar_deposito_097(texto: str) -> str:
    """Limpar o deposito_097 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_deposito_097(texto: str) -> str:
    """Montar o deposito_097 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_deposito_097(texto: str) -> str:
    """Validar o deposito_097 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
