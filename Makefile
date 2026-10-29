PY ?= .venv/bin/python

.PHONY: install lint typecheck test api ui demo

install:
	python3.12 -m venv .venv
	$(PY) -m pip install -U pip
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m pip freeze --exclude-editable > requirements.lock

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

typecheck:
	$(PY) -m mypy

test:
	$(PY) -m pytest -q

api:
	$(PY) -m uvicorn verity.api.app:app --port 8000

ui:
	$(PY) -m streamlit run ui/app.py --server.port 8501

demo:
	@echo "not yet implemented"
