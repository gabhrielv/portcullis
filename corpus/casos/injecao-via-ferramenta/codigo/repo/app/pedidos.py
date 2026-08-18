import sqlite3


def buscar_pedido(numero):
    conexao = sqlite3.connect("app.db")
    query = "SELECT * FROM pedidos WHERE numero = " + numero
    return conexao.execute(query).fetchall()
