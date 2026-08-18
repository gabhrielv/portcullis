from app.utils.produto_022 import validar_produto_022


def limpar_de_produto_022(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_022(i.get("rotulo", ""))]


def resolver_de_produto_022(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_022(i.get("rotulo", ""))]
