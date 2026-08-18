from app.utils.remessa_014 import validar_remessa_014


def resolver_de_remessa_014(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_014(i.get("rotulo", ""))]


def limpar_de_remessa_014(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_014(i.get("rotulo", ""))]
