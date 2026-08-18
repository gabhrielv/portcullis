from app.utils.endereco_110 import validar_endereco_110


def sanitizar_de_endereco_110(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_110(i.get("rotulo", ""))]


def checar_de_endereco_110(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_110(i.get("rotulo", ""))]
