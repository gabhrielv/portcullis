from app.utils.produto_042 import validar_produto_042


def resolver_de_produto_042(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_042(i.get("rotulo", ""))]


def validar_de_produto_042(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_042(i.get("rotulo", ""))]
