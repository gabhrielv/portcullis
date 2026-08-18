from app.utils.endereco_010 import validar_endereco_010


def montar_de_endereco_010(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_010(i.get("rotulo", ""))]


def sanitizar_de_endereco_010(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_010(i.get("rotulo", ""))]
