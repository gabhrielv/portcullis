from flask import Flask, request
from markupsafe import Markup

app = Flask(__name__)


@app.route("/carrinho")
def carrinho():
    # int() levanta ValueError em qualquer coisa que nao seja numero, entao o
    # que chega no Markup so pode ser digito. A lista de sanitizadores da
    # regra conhece escape() e render_template(), e nao conhece int().
    quantidade = int(request.args.get("qtd", "0"))
    return Markup("<span class='qtd'>" + str(quantidade) + "</span>")
