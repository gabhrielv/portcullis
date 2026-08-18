from app.utils.remessa_134 import validar_remessa_134


def limpar_de_remessa_134(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_134(i.get("rotulo", ""))]


def checar_de_remessa_134(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_remessa_134(i.get("rotulo", ""))]
