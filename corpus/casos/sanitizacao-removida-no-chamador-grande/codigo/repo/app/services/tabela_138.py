from app.utils.tabela_138 import validar_tabela_138


def checar_de_tabela_138(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de checar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_138(i.get("rotulo", ""))]


def limpar_de_tabela_138(itens: list[dict]) -> list[dict]:
    """Aplica o filtro de limpar sobre a lista ja carregada."""
    return [i for i in itens if validar_tabela_138(i.get("rotulo", ""))]
