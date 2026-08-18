from app.utils.carrinho_106 import validar_carrinho_106


def montar_de_carrinho_106(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_106(i.get("rotulo", ""))]


def checar_de_carrinho_106(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_106(i.get("rotulo", ""))]
