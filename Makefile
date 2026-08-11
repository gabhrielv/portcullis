PY := .venv/bin/python
MARCA := .venv/.instalado

.PHONY: instalar teste teste-integracao lint imagem infra destruir

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

teste-integracao: $(MARCA)
	cd app && ../$(PY) -m pytest -v -m integracao

lint: $(MARCA)
	cd app && ../$(PY) -m ruff check src tests

imagem:
	docker build -f docker/analisador.Dockerfile -t aduana-analisador:local .

infra:
	cd infra && terraform apply

destruir:
	cd infra && terraform destroy
