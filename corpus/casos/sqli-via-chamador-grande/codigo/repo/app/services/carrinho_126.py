from app.utils.carrinho_126 import validar_carrinho_126


def validar_de_carrinho_126(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_126(i.get("rotulo", ""))]


def checar_de_carrinho_126(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_126(i.get("rotulo", ""))]
