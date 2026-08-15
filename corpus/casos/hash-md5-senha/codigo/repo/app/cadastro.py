import hashlib


class Usuario:
    def set_password(self, digest):
        self._senha = digest


def cadastrar(usuario: Usuario, senha: str) -> Usuario:
    usuario.set_password(hashlib.md5(senha.encode()).hexdigest())
    return usuario
