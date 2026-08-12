PY := .venv/bin/python
MARCA := .venv/.instalado
REGRAS := build/regras.yaml
URL_REGRAS := https://semgrep.dev/c/p/default

.PHONY: instalar teste teste-integracao lint regras imagem infra destruir

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

# Regras congeladas num arquivo: `--config=auto` muda sem aviso e exige rede,
# o que tornaria o corpus da D12 irreproduzível.
$(REGRAS):
	mkdir -p build
	curl -sSL $(URL_REGRAS) -o $(REGRAS)

regras: $(REGRAS)

teste-integracao: $(MARCA) $(REGRAS)
	cd app && ADUANA_REGRAS=$(CURDIR)/$(REGRAS) ../$(PY) -m pytest -v -m integracao

lint: $(MARCA)
	cd app && ../$(PY) -m ruff check src tests

imagem:
	docker build -f docker/analisador.Dockerfile -t aduana-analisador:local .

infra:
	cd infra && terraform apply

destruir:
	cd infra && terraform destroy
