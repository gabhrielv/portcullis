PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_cliente_021(texto: str) -> str:
    """Montar o cliente_021 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_cliente_021(texto: str) -> str:
    """Limpar o cliente_021 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_cliente_021(texto: str) -> str:
    """Validar o cliente_021 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
