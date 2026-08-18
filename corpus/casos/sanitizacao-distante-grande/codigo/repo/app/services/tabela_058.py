from app.utils.tabela_058 import validar_tabela_058


def checar_de_tabela_058(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_058(i.get("rotulo", ""))]


def limpar_de_tabela_058(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_058(i.get("rotulo", ""))]
