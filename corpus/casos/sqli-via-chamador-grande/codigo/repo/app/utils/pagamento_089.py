PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_pagamento_089(texto: str) -> str:
    """Montar o pagamento_089 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_pagamento_089(texto: str) -> str:
    """Sanitizar o pagamento_089 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_pagamento_089(texto: str) -> str:
    """Validar o pagamento_089 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
