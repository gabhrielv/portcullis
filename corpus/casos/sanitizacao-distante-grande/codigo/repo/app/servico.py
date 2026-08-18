from app.db import por_id


def carregar_perfil(identificador):
    return {"perfil": por_id(identificador)}
