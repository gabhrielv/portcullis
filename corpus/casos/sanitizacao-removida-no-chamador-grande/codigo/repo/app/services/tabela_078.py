from app.utils.tabela_078 import validar_tabela_078


def montar_de_tabela_078(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de montar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_078(i.get("rotulo", ""))]


def sanitizar_de_tabela_078(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_078(i.get("rotulo", ""))]
