from app.utils.produto_062 import validar_produto_062


def normalizar_de_produto_062(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_062(i.get("rotulo", ""))]


def montar_de_produto_062(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_062(i.get("rotulo", ""))]
