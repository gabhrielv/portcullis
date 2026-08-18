from flask import Flask, request

from app.busca import buscar_por_termo

app = Flask(__name__)


@app.route("/buscar")
def buscar():
    return {"itens": buscar_por_termo(request.args["q"])}
