PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_devolucao_033(texto: str) -> str:
    """Montar o devolucao_033 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_devolucao_033(texto: str) -> str:
    """Limpar o devolucao_033 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def normalizar_devolucao_033(texto: str) -> str:
    """Normalizar o devolucao_033 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
