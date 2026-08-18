PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def validar_pagamento_129(texto: str) -> str:
    """Validar o pagamento_129 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_pagamento_129(texto: str) -> str:
    """Normalizar o pagamento_129 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_pagamento_129(texto: str) -> str:
    """Checar o pagamento_129 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
