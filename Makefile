.PHONY: install test lint run
install:
	python -m pip install -e ".[dev]"
test:
	pytest -q
lint:
	ruff check backend workers engines ai agents shared tests
run:
	uvicorn backend.main:app --reload
