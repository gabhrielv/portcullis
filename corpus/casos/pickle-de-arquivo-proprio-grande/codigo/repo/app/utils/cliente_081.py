PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def resolver_cliente_081(texto: str) -> str:
    """Resolver o cliente_081 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_cliente_081(texto: str) -> str:
    """Montar o cliente_081 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_cliente_081(texto: str) -> str:
    """Limpar o cliente_081 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
