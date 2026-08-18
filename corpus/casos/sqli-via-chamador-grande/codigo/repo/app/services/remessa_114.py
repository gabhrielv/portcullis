from app.utils.remessa_114 import validar_remessa_114


def normalizar_de_remessa_114(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_114(i.get("rotulo", ""))]


def montar_de_remessa_114(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_114(i.get("rotulo", ""))]
