from flask import Flask, request

from app.middleware import validar_id
from app.servico import carregar_perfil

app = Flask(__name__)
app.before_request(validar_id)


@app.route("/perfil")
def perfil():
    return carregar_perfil(request.args["id"])
