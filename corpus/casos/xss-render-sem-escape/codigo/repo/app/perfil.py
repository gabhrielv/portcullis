from flask import Flask, request
from markupsafe import Markup

app = Flask(__name__)


@app.route("/saudacao")
def saudacao():
    nome = request.args.get("nome", "")
    return Markup("<h1>Ola, " + nome + "</h1>")
