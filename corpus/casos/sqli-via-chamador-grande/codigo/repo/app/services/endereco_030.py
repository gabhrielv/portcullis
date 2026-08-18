from app.utils.endereco_030 import validar_endereco_030


def validar_de_endereco_030(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_030(i.get("rotulo", ""))]


def normalizar_de_endereco_030(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_030(i.get("rotulo", ""))]
