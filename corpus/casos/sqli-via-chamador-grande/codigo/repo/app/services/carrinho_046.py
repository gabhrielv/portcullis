from app.utils.carrinho_046 import validar_carrinho_046


def validar_de_carrinho_046(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_046(i.get("rotulo", ""))]


def montar_de_carrinho_046(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_046(i.get("rotulo", ""))]
