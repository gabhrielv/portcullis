from flask import abort, request


def validar_id():
    """Roda antes de toda requisicao. E aqui que a entrada deixa de ser livre."""
    identificador = request.args.get("id", "")
    if not identificador.isdigit():
        abort(400, "id precisa ser numerico")
