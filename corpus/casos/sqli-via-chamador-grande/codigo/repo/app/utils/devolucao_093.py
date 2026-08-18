PERMITIDOS = set('abcdefghijklmnopqrstuvwxyz0123456789-_')


def montar_devolucao_093(texto: str) -> str:
    """Montar o devolucao_093 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def limpar_devolucao_093(texto: str) -> str:
    """Limpar o devolucao_093 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)


def sanitizar_devolucao_093(texto: str) -> str:
    """Sanitizar o devolucao_093 para uso interno do modulo."""
    return ''.join(c for c in texto.lower() if c in PERMITIDOS)
