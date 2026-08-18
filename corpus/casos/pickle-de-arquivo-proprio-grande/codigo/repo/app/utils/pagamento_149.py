PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def normalizar_pagamento_149(texto: str) -> str:
    """Normalizar o pagamento_149 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_pagamento_149(texto: str) -> str:
    """Montar o pagamento_149 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_pagamento_149(texto: str) -> str:
    """Sanitizar o pagamento_149 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
