# If I Disappear: common tasks. Run `make help`.
SHELL := /bin/bash
PY ?= python3
VENV := .venv
VPY := $(VENV)/bin/python
API := services/api
WEB := apps/web

.PHONY: help setup api web dev serve test lint format typecheck build eval eval-live smoke a11y bench lighthouse live-check live-models live-browser screenshots og diagrams docker docker-run deploy-setup deploy clean

help: ## show this list
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

setup: ## create the Python venv and install everything (API, web)
	$(PY) -m venv $(VENV)
	$(VPY) -m pip install -U pip
	$(VPY) -m pip install -r $(API)/requirements-dev.txt
	cd $(WEB) && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci

api: ## run the API on :8080 (loads services/api/.env if present)
	cd $(API) && set -a && { [ -f .env ] && source .env || true; } && set +a && \
		../../$(VENV)/bin/uvicorn app.main:app --reload --port 8080

web: ## run the web app on :5173 (proxies /api to :8080)
	cd $(WEB) && npm run dev

dev: ## run API and web together (Ctrl+C stops both)
	@trap 'kill 0' EXIT; $(MAKE) --no-print-directory api & $(MAKE) --no-print-directory web & wait

serve: build ## build the web app and serve everything from the API on :8080 (like production)
	cd $(API) && set -a && { [ -f .env ] && source .env || true; } && set +a && \
		STATIC_DIR=../../$(WEB)/dist ../../$(VENV)/bin/uvicorn app.main:app --port 8080

test: ## run the API test suite (no network, no model)
	cd $(API) && AI_MODE=fixture ../../$(VPY) -m pytest

lint: ## ruff (API and eval harness) and TypeScript checks
	cd $(API) && ../../$(VENV)/bin/ruff check app tests && ../../$(VENV)/bin/ruff format --check app tests
	$(VENV)/bin/ruff check --select E,F,I,B,UP --ignore E501,B008,B904,UP042 --line-length 140 evals
	cd $(WEB) && npm run typecheck

format: ## format Python code
	cd $(API) && ../../$(VENV)/bin/ruff format app tests && ../../$(VENV)/bin/ruff check --fix app tests
	$(VENV)/bin/ruff format --line-length 140 evals

typecheck: ## TypeScript only
	cd $(WEB) && npm run typecheck

build: ## production build of the web app (apps/web/dist)
	cd $(WEB) && npm run build

eval: ## evaluation report without model calls -> evals/reports/latest.md
	AI_MODE=fixture $(VPY) -m evals.run

eval-live: ## evaluation report including Gemini on the benchmark sources (needs GEMINI_API_KEY)
	$(VPY) -m evals.run --live

live-check: ## every model and every AI path with a real key -> evals/reports/live-check.md (VOICE=note.wav optional)
	$(VPY) -m evals.live_check $(if $(VOICE),--voice $(VOICE),)

live-models: ## extraction quality per model on the benchmark (needs GEMINI_API_KEY; about 30 requests per model)
	$(VPY) -m evals.live_models

BASE ?= http://localhost:8080
smoke: ## browser end-to-end test of every main flow (needs `make serve` running)
	cd $(WEB) && node scripts/smoke.mjs $(BASE) ../../.smoke

a11y: ## accessibility check (axe-core, WCAG 2.2 AA) of every screen, light and dark (needs `make serve` running)
	cd $(WEB) && node scripts/a11y.mjs $(BASE)

bench: ## API response times -> evals/reports/api-benchmark.md (needs `make serve` running, AUTH_MODE=dev)
	$(VPY) -m evals.bench_api $(BASE)

lighthouse: ## Lighthouse on four pages, phone and desktop -> evals/reports/lighthouse.md (needs `make serve` and Node)
	$(VPY) -m evals.lighthouse_report $(BASE)

live-browser: ## live flows in a real browser: photo, voice note, AI review, grading, spoken practice (server with a key)
	cd $(WEB) && node scripts/live-browser.mjs $(BASE) ../../.live-browser

screenshots: ## screenshots of every screen, light and dark, desktop and phone (needs `make serve` running)
	cd $(WEB) && FORMAT=jpeg QUALITY=78 FULL=0 node scripts/screenshots.mjs $(BASE) ../../docs/screenshots

og: ## render the social preview image (apps/web/public/og.png)
	cd $(WEB) && node scripts/render-og.mjs

diagrams: ## draw docs/diagrams/*.png from docs/diagrams/src (Mermaid and HTML)
	cd $(WEB) && node scripts/render-diagrams.mjs

docker: ## build the single container (web + API)
	docker build -t if-i-disappear .

docker-run: ## run the container locally on :8080 (offline demo unless GEMINI_API_KEY is set)
	docker run --rm -p 8080:8080 -e SESSION_SECRET=local-only-change-me -e GEMINI_API_KEY if-i-disappear

deploy-setup: ## one-time Google Cloud setup (reads infra/config.sh)
	bash infra/setup.sh

deploy: ## build with Cloud Build and deploy to Cloud Run (reads infra/config.sh)
	bash infra/deploy.sh

clean: ## remove build outputs and caches
	rm -rf $(WEB)/dist $(API)/.data .pytest_cache $(API)/.pytest_cache .smoke .live-browser
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
