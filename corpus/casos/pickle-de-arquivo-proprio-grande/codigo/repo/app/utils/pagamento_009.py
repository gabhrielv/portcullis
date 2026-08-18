PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def checar_pagamento_009(texto: str) -> str:
    """Checar o pagamento_009 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_pagamento_009(texto: str) -> str:
    """Validar o pagamento_009 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def montar_pagamento_009(texto: str) -> str:
    """Montar o pagamento_009 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
