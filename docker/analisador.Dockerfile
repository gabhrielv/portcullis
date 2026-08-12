FROM python:3.12-slim

# git NÃO é instalado de propósito: o container não clona nada (D14).
RUN pip install --no-cache-dir semgrep==1.172.0

WORKDIR /opt/aduana
COPY app/pyproject.toml ./
COPY app/src ./src
# Perfil `analisador`: só boto3. Sem requests, sem PyJWT — o container não
# fala com o GitHub.
RUN pip install --no-cache-dir ".[analisador]"

# Regras vindas de build/regras (`make regras`), não baixadas aqui: a imagem
# carrega o mesmo conjunto que foi testado, e a construção roda sem rede.
COPY build/regras /opt/aduana/regras
ENV ADUANA_REGRAS=/opt/aduana/regras/default.yaml,/opt/aduana/regras/security-audit.yaml

# O filesystem da imagem é só-leitura em produção (T8); tudo que o processo
# escreve vai para /tmp, inclusive o que o semgrep queira cachear.
ENV HOME=/tmp
ENV SEMGREP_SETTINGS_FILE=/tmp/semgrep_settings.yml

# Roda como não-root: ele lê código de estranho.
RUN useradd --create-home --uid 10001 analista
USER analista

ENTRYPOINT ["python", "-m", "aduana.analisador.main"]
CMD ["/entrada", "/saida"]
