import sqlite3


def relatorio(tipo_id: int):
    conexao = sqlite3.connect("app.db")
    return conexao.execute("SELECT * FROM vendas WHERE tipo_id = ?", (tipo_id,)).fetchall()
