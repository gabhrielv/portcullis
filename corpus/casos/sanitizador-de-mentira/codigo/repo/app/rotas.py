from flask import Flask, request

from app.relatorios import por_cliente
from app.seguranca import validar

app = Flask(__name__)


@app.route("/relatorios")
def relatorios():
    return {"linhas": por_cliente(validar(request.args["cliente"]))}
