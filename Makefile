.PHONY: setup build up down logs test clean migrate

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

clean:
	docker-compose -f infrastructure/docker-compose.yml down -v
	rm -f test_kravigil.db

migrate:
	alembic revision --autogenerate -m "Auto migration"
	alembic upgrade head
