from app.utils.carrinho_066 import validar_carrinho_066


def montar_de_carrinho_066(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_066(i.get("rotulo", ""))]


def limpar_de_carrinho_066(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_066(i.get("rotulo", ""))]
