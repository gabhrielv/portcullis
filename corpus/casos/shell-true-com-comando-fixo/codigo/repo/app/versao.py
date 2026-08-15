import subprocess

PARTES = ["git", "describe", "--tags", "--always"]


def versao_do_git() -> str:
    """shell=True para herdar o PATH do ambiente do container.

    Todas as partes do comando sao literais da constante acima. Nao existe
    parametro, nem leitura de ambiente, nem nada vindo de requisicao.
    """
    saida = subprocess.run(
        " ".join(PARTES), shell=True, capture_output=True, text=True, check=False
    )
    return saida.stdout.strip()
