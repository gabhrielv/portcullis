import sqlite3

from app.tipos import Periodo


def totais(periodo: Periodo):
    conexao = sqlite3.connect("app.db")
    # O semgrep dispara aqui: é montagem de SQL por concatenação. Mas o único
    # valor que chega é o `.value` de um membro do Enum acima, e não existe
    # caminho por onde uma requisição escolha esse valor.
    query = "SELECT SUM(valor) FROM vendas WHERE periodo = '" + periodo.value + "'"
    return conexao.execute(query).fetchone()
