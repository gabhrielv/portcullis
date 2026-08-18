from app.utils.endereco_090 import validar_endereco_090


def sanitizar_de_endereco_090(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_090(i.get("rotulo", ""))]


def checar_de_endereco_090(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_090(i.get("rotulo", ""))]
