from flask import Flask

from app.indice import carregar_indice

app = Flask(__name__)


@app.route("/indice")
def ver_indice():
    return {"total": len(carregar_indice())}
