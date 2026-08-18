from app.utils.tabela_018 import validar_tabela_018


def normalizar_de_tabela_018(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de normalizar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_018(i.get("rotulo", ""))]


def resolver_de_tabela_018(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de resolver sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_018(i.get("rotulo", ""))]
