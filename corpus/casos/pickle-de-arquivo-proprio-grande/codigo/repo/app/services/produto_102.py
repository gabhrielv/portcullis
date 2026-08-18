from app.utils.produto_102 import validar_produto_102


def normalizar_de_produto_102(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_102(i.get("rotulo", ""))]


def montar_de_produto_102(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_102(i.get("rotulo", ""))]
