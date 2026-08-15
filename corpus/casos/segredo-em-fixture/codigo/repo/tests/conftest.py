import pytest

# Credencial inventada para a suite. O ambiente sobe um S3 falso em memoria,
# e nenhuma chamada de rede sai daqui.
AWS_SECRET_ACCESS_KEY = "Qw8zTm4pLxCv2RnGb6YhKd1FsJa9UeWo3ZbPiNrM"


@pytest.fixture
def credenciais_falsas():
    return {"chave": AWS_SECRET_ACCESS_KEY, "regiao": "us-east-1"}
