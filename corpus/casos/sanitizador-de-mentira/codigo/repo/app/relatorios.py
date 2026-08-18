import sqlite3


def por_cliente(nome):
    conexao = sqlite3.connect("app.db")
    query = "SELECT id, total FROM pedidos WHERE cliente = '" + nome + "'"
    return conexao.execute(query).fetchall()
