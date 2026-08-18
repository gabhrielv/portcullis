PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_deposito_117(texto: str) -> str:
    """Montar o deposito_117 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_deposito_117(texto: str) -> str:
    """Normalizar o deposito_117 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_deposito_117(texto: str) -> str:
    """Limpar o deposito_117 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
