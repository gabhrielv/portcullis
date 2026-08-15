from flask import Flask, request

from app.db import por_id

app = Flask(__name__)


@app.route("/conta")
def conta():
    return {"conta": por_id(request.args["id"])}
