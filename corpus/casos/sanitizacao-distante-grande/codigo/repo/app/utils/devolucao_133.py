PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def checar_devolucao_133(texto: str) -> str:
    """Checar o devolucao_133 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_devolucao_133(texto: str) -> str:
    """Limpar o devolucao_133 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def validar_devolucao_133(texto: str) -> str:
    """Validar o devolucao_133 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
