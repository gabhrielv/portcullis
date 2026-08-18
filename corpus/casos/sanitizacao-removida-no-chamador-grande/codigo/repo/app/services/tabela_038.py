from app.utils.tabela_038 import validar_tabela_038


def checar_de_tabela_038(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_038(i.get("rotulo", ""))]


def sanitizar_de_tabela_038(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de sanitizar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_038(i.get("rotulo", ""))]
