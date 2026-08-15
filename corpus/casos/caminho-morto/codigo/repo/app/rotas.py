from flask import Flask, request

from app.relatorio import relatorio

app = Flask(__name__)


@app.route("/relatorio")
def ver_relatorio():
    return {"linhas": relatorio(int(request.args["tipo"]))}
