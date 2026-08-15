import os


def chave():
    """Em producao a credencial vem do ambiente, nunca do codigo."""
    return os.environ["AWS_SECRET_ACCESS_KEY"]
