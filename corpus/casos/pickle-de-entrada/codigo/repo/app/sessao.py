import pickle

from flask import Flask, request

app = Flask(__name__)


@app.route("/restaurar", methods=["POST"])
def restaurar():
    estado = pickle.loads(request.get_data())
    return {"restaurado": str(estado)}
