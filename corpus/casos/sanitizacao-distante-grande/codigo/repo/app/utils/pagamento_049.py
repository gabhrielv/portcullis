PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def sanitizar_pagamento_049(texto: str) -> str:
    """Sanitizar o pagamento_049 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_pagamento_049(texto: str) -> str:
    """Limpar o pagamento_049 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def checar_pagamento_049(texto: str) -> str:
    """Checar o pagamento_049 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
