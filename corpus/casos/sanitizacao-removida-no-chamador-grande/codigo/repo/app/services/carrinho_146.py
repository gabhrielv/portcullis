from app.utils.carrinho_146 import validar_carrinho_146


def sanitizar_de_carrinho_146(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_146(i.get("rotulo", ""))]


def validar_de_carrinho_146(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_146(i.get("rotulo", ""))]
