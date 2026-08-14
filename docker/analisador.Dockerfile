# Imagem base da AWS: ela já traz o cliente da Runtime API, que é o que
# transforma um container em Lambda. Construir sobre python:3.12-slim exigiria
# instalar e configurar o `awslambdaric` na mão, sem ganho nenhum.
FROM public.ecr.aws/lambda/python:3.12

# git NÃO é instalado de propósito: o analisador não clona nada.
RUN pip install --no-cache-dir semgrep==1.172.0

WORKDIR /opt/portcullis
COPY app/pyproject.toml ./
COPY app/src ./src
# Perfil `analisador`: só boto3. Sem requests, sem PyJWT — ele lê código de
# estranho e não tem como falar com o GitHub nem por acidente.
RUN pip install --no-cache-dir ".[analisador]"

# Regras vindas de build/regras (`make regras`), não baixadas aqui: a imagem
# carrega o mesmo conjunto que foi testado, e a construção roda sem rede.
COPY build/regras /opt/portcullis/regras
ENV PORTCULLIS_REGRAS=/opt/portcullis/regras/default.yaml,/opt/portcullis/regras/security-audit.yaml

# Na Lambda o filesystem é só-leitura fora de /tmp. Sem estas duas, o semgrep
# tenta escrever configuração no HOME e morre com erro que não diz isso.
ENV HOME=/tmp
ENV SEMGREP_SETTINGS_FILE=/tmp/semgrep_settings.yml

# Sem `USER`: a imagem base da AWS não define um, e o isolamento que o usuário
# não-root dava aqui a Lambda já dá de forma mais forte — cada invocação roda
# numa microVM descartável, com o filesystem só-leitura fora de /tmp.
CMD ["portcullis.analisador.main.lambda_handler"]
