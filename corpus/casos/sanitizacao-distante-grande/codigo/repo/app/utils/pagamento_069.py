PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_pagamento_069(texto: str) -> str:
    """Montar o pagamento_069 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_pagamento_069(texto: str) -> str:
    """Normalizar o pagamento_069 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def resolver_pagamento_069(texto: str) -> str:
    """Resolver o pagamento_069 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
