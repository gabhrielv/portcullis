from app.utils.tabela_118 import validar_tabela_118


def normalizar_de_tabela_118(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_118(i.get("rotulo", ""))]


def validar_de_tabela_118(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de validar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_118(i.get("rotulo", ""))]
