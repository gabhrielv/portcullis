PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def limpar_cliente_121(texto: str) -> str:
    """Limpar o cliente_121 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_cliente_121(texto: str) -> str:
    """Checar o cliente_121 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_cliente_121(texto: str) -> str:
    """Montar o cliente_121 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
