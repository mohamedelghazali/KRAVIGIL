.PHONY: setup build up down logs test lint format clean migrate seed deploy-prod replicate-minio

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

build:
	docker-compose -f infrastructure/docker-compose.yml build

up:
	docker-compose -f infrastructure/docker-compose.yml up -d

down:
	docker-compose -f infrastructure/docker-compose.yml down

logs:
	docker-compose -f infrastructure/docker-compose.yml logs -f

test:
	pytest tests/ -v

lint:
	ruff check backend/ ai/ workers/ engines/
	mypy backend/ ai/ --ignore-missing-imports

format:
	black backend/ ai/ workers/ engines/

clean:
	docker-compose -f infrastructure/docker-compose.yml down -v
	rm -f test_kravigil.db

migrate:
	alembic revision --autogenerate -m "Auto migration"
	alembic upgrade head

seed:
	python scripts/seed_db.py

deploy-prod:
	./scripts/deploy_prod.sh

replicate-minio:
	./infrastructure/minio/replicate.sh