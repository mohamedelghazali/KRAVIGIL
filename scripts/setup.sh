#!/bin/bash

set -e

echo "[*] Setting up KRAVIGIL Development Environment..."

if [ ! -f .env ]; then
    echo "[*] Creating .env file from template..."
    cp .env.example .env
    echo "[!] IMPORTANT: Edit .env and set secure passwords/keys before deployment."
fi

echo "[*] Building Docker containers..."
docker-compose -f infrastructure/docker-compose.yml build

echo "[*] Starting services..."
docker-compose -f infrastructure/docker-compose.yml up -d

echo "[*] Waiting for database to be ready..."
sleep 10

echo "[*] Running database migrations..."
# Assuming migrations are handled via alembic
# docker-compose exec backend alembic upgrade head

echo "[*] Seeding initial database..."
docker-compose exec backend python /app/scripts/seed_db.py

echo "[+] Setup complete. Access KRAVIGIL at http://localhost"
