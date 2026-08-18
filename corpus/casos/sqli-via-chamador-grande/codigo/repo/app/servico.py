from app.db import por_id


def carregar_conta(identificador):
    return {"conta": por_id(identificador)}
