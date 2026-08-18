from app.utils.endereco_070 import validar_endereco_070


def normalizar_de_endereco_070(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_070(i.get("rotulo", ""))]


def resolver_de_endereco_070(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_070(i.get("rotulo", ""))]
