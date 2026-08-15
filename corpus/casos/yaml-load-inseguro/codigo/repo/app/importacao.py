import yaml
from flask import Flask, request

app = Flask(__name__)


@app.route("/importar", methods=["POST"])
def importar():
    definicao = yaml.load(request.get_data())
    return {"itens": len(definicao)}
