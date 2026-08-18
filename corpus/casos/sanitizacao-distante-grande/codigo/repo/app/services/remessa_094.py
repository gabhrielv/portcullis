from app.utils.remessa_094 import validar_remessa_094


def sanitizar_de_remessa_094(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_094(i.get("rotulo", ""))]


def normalizar_de_remessa_094(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_094(i.get("rotulo", ""))]
