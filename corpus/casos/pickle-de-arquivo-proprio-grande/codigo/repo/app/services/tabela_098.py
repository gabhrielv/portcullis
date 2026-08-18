from app.utils.tabela_098 import validar_tabela_098


def normalizar_de_tabela_098(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_098(i.get("rotulo", ""))]


def checar_de_tabela_098(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_098(i.get("rotulo", ""))]
