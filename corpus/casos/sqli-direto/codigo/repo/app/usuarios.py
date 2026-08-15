import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/usuario")
def buscar_usuario():
    conexao = sqlite3.connect("app.db")
    identificador = request.args.get("id")
    query = "SELECT nome, email FROM usuarios WHERE id = " + identificador
    return conexao.execute(query).fetchall()
