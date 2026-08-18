PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def resolver_pagamento_109(texto: str) -> str:
    """Resolver o pagamento_109 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_pagamento_109(texto: str) -> str:
    """Montar o pagamento_109 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_pagamento_109(texto: str) -> str:
    """Normalizar o pagamento_109 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
