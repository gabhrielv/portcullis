from flask import Flask, request

from app.servico import carregar_conta

app = Flask(__name__)


@app.route("/conta")
def conta():
    return carregar_conta(request.args["id"])
