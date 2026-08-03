.PHONY: run test lint format typecheck check clean demo-db demo-test demo-smoke demo-up demo-release

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

demo-db:
	python scripts/create_synthetic_demo.py

demo-test:
	pytest tests/test_demo_data.py -q

demo-smoke:
	python scripts/run_demo_smoke.py

demo-up:
	docker compose --profile local up --build

demo-release:
	pytest -q
	ruff check src tests scripts
	npm --prefix frontend test -- --run
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
