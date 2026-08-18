from app.utils.produto_122 import validar_produto_122


def sanitizar_de_produto_122(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_122(i.get("rotulo", ""))]


def validar_de_produto_122(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_122(i.get("rotulo", ""))]
