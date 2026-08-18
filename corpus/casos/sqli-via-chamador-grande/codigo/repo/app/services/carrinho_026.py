from app.utils.carrinho_026 import validar_carrinho_026


def checar_de_carrinho_026(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_026(i.get("rotulo", ""))]


def montar_de_carrinho_026(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_carrinho_026(i.get("rotulo", ""))]
