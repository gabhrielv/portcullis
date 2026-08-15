import subprocess

from flask import Flask, request

app = Flask(__name__)


@app.route("/ping")
def ping():
    destino = request.args.get("host")
    saida = subprocess.run("ping -c 1 " + destino, shell=True, capture_output=True)
    return saida.stdout
