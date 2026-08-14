PY := .venv/bin/python
# terraform e aws foram instalados em ~/.local/bin, sem sudo.
TF := $(shell command -v terraform 2>/dev/null || echo $(HOME)/.local/bin/terraform)
MARCA := .venv/.instalado
DIR_REGRAS := build/regras
REGRAS := $(DIR_REGRAS)/default.yaml $(DIR_REGRAS)/security-audit.yaml
# Os dois conjuntos não se contêm: medido em 12/08/2026, cada um acha ERROR
# que o outro não acha. Rodar os dois custa o mesmo tempo.
PORTCULLIS_REGRAS := $(CURDIR)/$(DIR_REGRAS)/default.yaml,$(CURDIR)/$(DIR_REGRAS)/security-audit.yaml

.PHONY: instalar teste teste-integracao lint regras imagem validar-infra infra destruir

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

lint: $(MARCA)
	cd app && ../$(PY) -m ruff check src tests

imagem: $(REGRAS)
	docker build -f docker/analisador.Dockerfile -t portcullis-analisador:local .

validar-infra:
	cd infra && $(TF) fmt -recursive -check && $(TF) validate

infra:
	cd infra && $(TF) apply

destruir:
	cd infra && $(TF) destroy
