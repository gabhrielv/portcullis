from app.utils.endereco_130 import validar_endereco_130


def normalizar_de_endereco_130(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_130(i.get("rotulo", ""))]


def resolver_de_endereco_130(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_130(i.get("rotulo", ""))]
