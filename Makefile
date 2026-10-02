# Common development tasks. Run `make help` to list them.
.DEFAULT_GOAL := help
PY := backend/.venv/bin/python

help:  ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup:  ## Install backend + frontend dependencies and pull the embedding model
	python3 -m venv backend/.venv
	$(PY) -m pip install -q -r backend/requirements-dev.txt
	cd frontend && npm install
	test -f backend/.env || cp backend/.env.example backend/.env
	ollama pull embeddinggemma

api:  ## Run the API on :8000 (reloads on change)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web:  ## Run the UI on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test:  ## Run backend tests (no models needed)
	cd backend && .venv/bin/python -m pytest -q

eval:  ## Retrieval/abstention eval against the configured models
	cd backend && .venv/bin/python -m eval.run_eval

lint:  ## Lint and format-check the backend
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .

build:  ## Production build of the UI
	cd frontend && npm run build

.PHONY: help setup api web test eval lint build
