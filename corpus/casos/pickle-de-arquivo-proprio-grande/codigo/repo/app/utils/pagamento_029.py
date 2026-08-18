PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def checar_pagamento_029(texto: str) -> str:
    """Checar o pagamento_029 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_pagamento_029(texto: str) -> str:
    """Validar o pagamento_029 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_pagamento_029(texto: str) -> str:
    """Limpar o pagamento_029 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
