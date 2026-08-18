PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_deposito_017(texto: str) -> str:
    """Montar o deposito_017 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_deposito_017(texto: str) -> str:
    """Limpar o deposito_017 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_deposito_017(texto: str) -> str:
    """Checar o deposito_017 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
