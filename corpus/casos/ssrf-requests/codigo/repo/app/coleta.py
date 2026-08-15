import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/espelhar")
def espelhar():
    destino = request.args["url"]
    return requests.get(destino, timeout=10).text
