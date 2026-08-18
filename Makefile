PYTHON ?= python3
VENV := .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

.PHONY: venv install run ci test check-js check-schema lint docker-build docker-up

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"

install: venv

run:
	$(PY) -m csm_dashboard

test:
	$(PYTEST) -q

check-js:
	node --check src/csm_dashboard/web/static/app.js
	node --check src/csm_dashboard/web/static/compose.js
	node --check src/csm_dashboard/web/static/worldclock.js

check-schema:
	$(PYTEST) -q tests/test_schema.py tests/test_openapi_paths.py

lint:
	$(PY) -m compileall -q src tests

ci: lint check-js test

docker-build:
	docker compose build

docker-up:
	docker compose up --build
