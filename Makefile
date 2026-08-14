PY := .venv/bin/python
# terraform e aws foram instalados em ~/.local/bin, sem sudo.
TF := $(shell command -v terraform 2>/dev/null || echo $(HOME)/.local/bin/terraform)
MARCA := .venv/.instalado
DIR_REGRAS := build/regras
REGRAS := $(DIR_REGRAS)/default.yaml $(DIR_REGRAS)/security-audit.yaml
# Os dois conjuntos não se contêm: medido em 12/08/2026, cada um acha ERROR
# que o outro não acha. Rodar os dois custa o mesmo tempo.
PORTCULLIS_REGRAS := $(CURDIR)/$(DIR_REGRAS)/default.yaml,$(CURDIR)/$(DIR_REGRAS)/security-audit.yaml

.PHONY: instalar teste teste-integracao lint regras imagem imagem-push \
        pacote-lambda validar-infra infra url-webhook destruir

.venv:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip

# Reinstala só quando o pyproject muda.
$(MARCA): app/pyproject.toml | .venv
	cd app && ../$(PY) -m pip install -e ".[dev,nuvem]"
	touch $(MARCA)

instalar: $(MARCA)

teste: $(MARCA)
	cd app && ../$(PY) -m pytest -v

# Regras num arquivo: `--config=auto` muda sem aviso e exige rede, o que
# tornaria o corpus da D12 irreproduzível.
$(DIR_REGRAS)/%.yaml:
	mkdir -p $(DIR_REGRAS)
	curl -sSL https://semgrep.dev/c/p/$* -o $@

regras: $(REGRAS)

teste-integracao: $(MARCA) $(REGRAS)
	cd app && PORTCULLIS_REGRAS="$(PORTCULLIS_REGRAS)" ../$(PY) -m pytest -v -m integracao

# `--config` explícito: scripts/ fica fora do alcance do app/pyproject.toml, e
# sem isto o ruff usaria o padrão lá e outra config aqui, discordando de si.
lint: $(MARCA)
	cd app && ../$(PY) -m ruff check --config pyproject.toml src tests ../scripts

imagem: $(REGRAS)
	docker build -f docker/analisador.Dockerfile -t portcullis-analisador:local .

# Um zip só para as quatro Lambdas de fora da VPC. O perfil `nuvem` traz
# requests e PyJWT; o boto3 sai porque o runtime python3.12 já tem ele.
#
# Sai a ÁRVORE INTEIRA dele, não só o pacote de cima: `/var/task` vem antes de
# `/var/runtime` no sys.path, então um dateutil ou jmespath solto aqui seria
# carregado pelo boto3 do runtime, em versão diferente da que ele espera.
# `bin/` são scripts de linha de comando que Lambda nenhuma executa.
LIXO_LAMBDA := boto3 botocore s3transfer jmespath dateutil six.py bin __pycache__

pacote-lambda: $(MARCA)
	rm -rf build/lambda build/lambda.zip
	mkdir -p build/lambda
	cd app && ../$(PY) -m pip install ".[nuvem]" --target ../build/lambda --quiet
	cd build/lambda && rm -rf $(LIXO_LAMBDA) \
	  boto3-*.dist-info botocore-*.dist-info s3transfer-*.dist-info \
	  jmespath-*.dist-info python_dateutil-*.dist-info six-*.dist-info
	cd build/lambda && zip -qr ../lambda.zip .
	@echo "build/lambda.zip: $$(du -h build/lambda.zip | cut -f1)"

validar-infra:
	cd infra && $(TF) fmt -recursive -check && $(TF) validate

infra: pacote-lambda
	cd infra && $(TF) apply

# Cada apply cria um API Gateway novo, com URL nova. Isto aponta o GitHub App
# para ela, autenticando com a chave privada que já está no SSM.
url-webhook:
	$(PY) scripts/atualizar_webhook.py \
	  --app-id "$$(cd infra && $(TF) output -raw github_app_id)" \
	  --url "$$(cd infra && $(TF) output -raw url_webhook)"

destruir:
	cd infra && $(TF) destroy

# A imagem precisa estar no ECR antes de a Lambda de container ser criada.
imagem-push: imagem
	$(eval REPO := $(shell cd infra && $(TF) output -raw url_repositorio_analisador))
	aws ecr get-login-password --region us-east-1 \
	  | docker login --username AWS --password-stdin $(REPO)
	docker tag portcullis-analisador:local $(REPO):local
	docker push $(REPO):local
