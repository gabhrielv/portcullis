from app.utils.remessa_034 import validar_remessa_034


def checar_de_remessa_034(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_034(i.get("rotulo", ""))]


def validar_de_remessa_034(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_034(i.get("rotulo", ""))]
