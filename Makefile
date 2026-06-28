# Convenience targets. Use python3 on Linux/macOS; on Windows run the commands directly.
PY ?= python

.PHONY: help install install-api install-dev pipeline test coverage lint format typecheck audit \
        validate backtest sensitivity fairness export init-db load serve up down logs

help:
	@echo "Targets:"
	@echo "  install      Install pipeline dependencies (requirements.txt)"
	@echo "  install-api  Install API dependencies (requirements-api.txt)"
	@echo "  install-dev  Install dev/CI tooling (requirements-dev.txt)"
	@echo "  test         Run unit tests"
	@echo "  coverage     Run tests with coverage report"
	@echo "  lint         Lint with ruff"
	@echo "  format       Auto-format with ruff"
	@echo "  typecheck    Static type check with mypy"
	@echo "  audit        Scan locked API deps for known CVEs (pip-audit)"
	@echo "  pipeline     Run the full data pipeline (download -> score -> validate -> analyze)"
	@echo "  validate     Run data validation checks"
	@echo "  backtest     Run the outcome-validation backtest"
	@echo "  sensitivity  Run the weight-sensitivity analysis"
	@echo "  fairness     Run the fairness audit"
	@echo "  export       Rebuild the web/API seed (app_data.json, boundaries.json)"
	@echo "  init-db      Create API tables + indexes (idempotent)"
	@echo "  load         Seed Postgres from data/processed"
	@echo "  serve        Run the API locally (uvicorn)"
	@echo "  up / down    Start / stop the full Docker stack"

install:
	$(PY) -m pip install -r requirements.txt

install-api:
	$(PY) -m pip install -r requirements-api.txt

install-dev:
	$(PY) -m pip install -r requirements-dev.txt

pipeline:
	$(PY) src/run_pipeline.py

test:
	$(PY) -m pytest -q

coverage:
	$(PY) -m pytest --cov=src --cov=waterapi --cov-report=term-missing --cov-report=xml

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff format .

typecheck:
	$(PY) -m mypy

audit:
	$(PY) -m pip_audit -r requirements-api.lock.txt

validate:
	$(PY) src/validate_outputs.py

backtest:
	$(PY) src/backtest.py

sensitivity:
	$(PY) src/sensitivity.py

fairness:
	$(PY) src/fairness_audit.py

export:
	$(PY) src/export_web_app_data.py

init-db:
	$(PY) -m waterapi.cli init-db

load:
	$(PY) -m waterapi.cli load

serve:
	$(PY) -m waterapi.cli serve

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api
