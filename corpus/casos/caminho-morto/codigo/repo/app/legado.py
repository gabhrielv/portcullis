import sqlite3


def relatorio_antigo(filtro):
    """Substituido pelo relatorio novo na migracao de 2024."""
    conexao = sqlite3.connect("app.db")
    query = "SELECT * FROM vendas WHERE tipo = '" + filtro + "'"
    return conexao.execute(query).fetchall()
