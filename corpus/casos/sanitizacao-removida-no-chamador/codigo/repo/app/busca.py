import sqlite3


def buscar_por_termo(termo):
    conexao = sqlite3.connect("app.db")
    query = "SELECT id, nome FROM itens WHERE nome LIKE '%" + termo + "%'"
    return conexao.execute(query).fetchall()
