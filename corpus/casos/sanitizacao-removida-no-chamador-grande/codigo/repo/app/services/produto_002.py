from app.utils.produto_002 import validar_produto_002


def checar_de_produto_002(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_002(i.get("rotulo", ""))]


def resolver_de_produto_002(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_002(i.get("rotulo", ""))]
