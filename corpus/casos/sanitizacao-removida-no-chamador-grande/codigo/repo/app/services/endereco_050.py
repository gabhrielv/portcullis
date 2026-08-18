from app.utils.endereco_050 import validar_endereco_050


def normalizar_de_endereco_050(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_050(i.get("rotulo", ""))]


def validar_de_endereco_050(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_endereco_050(i.get("rotulo", ""))]
