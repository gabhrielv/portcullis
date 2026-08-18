from app.utils.carrinho_006 import validar_carrinho_006


def checar_de_carrinho_006(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_006(i.get("rotulo", ""))]


def limpar_de_carrinho_006(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_006(i.get("rotulo", ""))]
