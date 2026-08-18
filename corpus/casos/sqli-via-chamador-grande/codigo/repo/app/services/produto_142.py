from app.utils.produto_142 import validar_produto_142


def normalizar_de_produto_142(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_142(i.get("rotulo", ""))]


def validar_de_produto_142(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_142(i.get("rotulo", ""))]
