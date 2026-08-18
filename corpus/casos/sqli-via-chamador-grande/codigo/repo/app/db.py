import sqlite3


def por_id(identificador):
    conexao = sqlite3.connect("app.db")
    query = "SELECT nome, saldo FROM contas WHERE id = " + identificador
    return conexao.execute(query).fetchone()
