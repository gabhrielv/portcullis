from app.utils.produto_082 import validar_produto_082


def limpar_de_produto_082(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_082(i.get("rotulo", ""))]


def validar_de_produto_082(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_produto_082(i.get("rotulo", ""))]
