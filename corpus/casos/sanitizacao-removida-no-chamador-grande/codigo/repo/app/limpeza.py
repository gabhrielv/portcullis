import re


def limpar(texto):
    """Remove tudo que nao for alfanumerico ou espaco."""
    return re.sub(r"[^A-Za-z0-9 ]", "", texto)
