from app.utils.carrinho_086 import validar_carrinho_086


def validar_de_carrinho_086(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_086(i.get("rotulo", ""))]


def resolver_de_carrinho_086(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_086(i.get("rotulo", ""))]
