import sqlite3


def relatorio_antigo(filtro):
    """Portado do servico legado neste PR. Ainda sem rota."""
    conexao = sqlite3.connect("app.db")
    query = "SELECT * FROM vendas WHERE tipo = '" + filtro + "'"
    return conexao.execute(query).fetchall()
