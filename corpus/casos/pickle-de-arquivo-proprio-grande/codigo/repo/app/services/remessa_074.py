from app.utils.remessa_074 import validar_remessa_074


def resolver_de_remessa_074(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_074(i.get("rotulo", ""))]


def montar_de_remessa_074(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_074(i.get("rotulo", ""))]
