from flask import Flask, request

app = Flask(__name__)

BASE = "/var/dados/"


@app.route("/baixar")
def baixar():
    nome = request.args.get("arquivo")
    with open(BASE + nome) as arquivo:
        return arquivo.read()
