.PHONY: run dev-local test lint format typecheck check clean demo-data demo-test demo-smoke demo-up demo-release

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-local:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-dev.ps1

test:
	pytest tests/ -v

demo-data:
	python scripts/generate_demo_mvp_data.py

demo-test:
	pytest tests/test_api/test_contract_v1.py tests/test_clinical/test_pdf_ingestion.py -q

demo-smoke:
	python scripts/run_demo_smoke.py

demo-up:
	docker compose --profile local up --build

demo-release:
	pytest -q
	ruff check src tests scripts
	npm --prefix frontend run lint
	npm --prefix frontend test -- --runInBand
	npm --prefix frontend run build
	python scripts/run_demo_smoke.py

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
