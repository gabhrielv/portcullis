from app.utils.remessa_054 import validar_remessa_054


def montar_de_remessa_054(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_054(i.get("rotulo", ""))]


def normalizar_de_remessa_054(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_054(i.get("rotulo", ""))]
