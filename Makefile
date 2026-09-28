# Recipes stay shell-neutral so they run under cmd.exe (Windows) and sh (Linux/CI).
ifeq ($(OS),Windows_NT)
  VENV_PY := .venv\Scripts\python.exe
else
  VENV_PY := .venv/bin/python
endif
PYTHON ?= python
NPM := npm --prefix frontend
PROJECTS ?= R1 R2

.PHONY: help setup env env-update up down logs lint format test test-integration e2e seed-library curator-review diff-report anexo-c-report form-templates anonymize pii-check

help:
	@echo "setup            .venv, dependencias Python, npm ci e Chromium do Playwright"
	@echo "env              cria o .env local com segredos aleatorios"
	@echo "env-update       acrescenta ao .env as variaveis novas do .env.example (sem mexer nas existentes)"
	@echo "up / down        arranca ou para a stack do docker compose"
	@echo "lint             ruff, mypy, eslint e tsc"
	@echo "test             pytest (backend + tools) e vitest; precisa da stack ligada (make up)"
	@echo "test-integration testes contra a stack ligada (make up)"
	@echo "e2e              Playwright"
	@echo "seed-library     propostas da base de conhecimento a partir de data/fixtures (R1, R2)"
	@echo "curator-review   escreve docs/revisao-curador.md a partir das propostas (depois de seed-library)"
	@echo "diff-report      escreve docs/fase4-diff-R1.md (R1 montado na stack, adaptativos gerados)"
	@echo "anexo-c-report   escreve docs/fase5-anexo-c.md (casos do Anexo C na validacao; precisa do Postgres)"
	@echo "form-templates   modelos vazios dos formularios a partir de R1 (data/fixtures)"
	@echo "anonymize        data/private/<PROJECTS> -> data/fixtures/<PROJECTS> (so localmente)"
	@echo "pii-check        procura padroes de dados pessoais em data/fixtures"

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e "backend[dev]" -r tools/requirements.txt
	$(NPM) ci
	cd frontend && npx playwright install chromium

env:
	$(PYTHON) tools/make_dev_env.py

env-update:
	$(PYTHON) tools/make_dev_env.py --add-missing

up:
	docker compose up -d --build --wait

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	$(VENV_PY) -m ruff check backend tools
	$(VENV_PY) -m ruff format --check backend tools
	$(VENV_PY) -m mypy backend/app backend/tests
	$(VENV_PY) -m mypy tools
	$(NPM) run lint
	$(NPM) run typecheck

format:
	$(VENV_PY) -m ruff format backend tools
	$(VENV_PY) -m ruff check --fix backend tools

test:
	$(VENV_PY) -m pytest
	$(NPM) run test

test-integration:
	$(VENV_PY) -m pytest -m integration backend/tests

e2e:
	$(NPM) run e2e

seed-library:
	docker compose exec backend python -m app.knowledge.seed

curator-review:
	docker compose exec -T backend python -m app.library.review_report > docs/revisao-curador.md

diff-report:
	docker compose exec -T backend python -m app.assembly.diff_report R1 > docs/fase4-diff-R1.md

anexo-c-report:
	$(VENV_PY) -m pytest -q backend/tests/test_validation_annex_c.py --annex-c-report=docs/fase5-anexo-c.md

form-templates:
	$(VENV_PY) -m app.forms.derive

anonymize:
	$(VENV_PY) tools/anonymize.py $(PROJECTS)

pii-check:
	$(VENV_PY) tools/anonymize.py --check data/fixtures
	$(VENV_PY) tools/anonymize.py --check backend/app/forms/templates
