#!/bin/bash

set -e

echo "[*] Starting KRAVIGIL Production Deployment..."

if [ ! -f .env ]; then
    echo "[-] .env file not found. Please create it with production secrets."
    exit 1
fi

source .env

if [ -z "$SECRET_KEY" ] || [ -z "$DB_PASSWORD" ] || [ -z "$REDIS_PASSWORD" ] || [ -z "$MINIO_PASSWORD" ]; then
    echo "[-] Missing required environment variables in .env"
    exit 1
fi

echo "[*] Building Docker images..."
docker-compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml build

echo "[*] Starting services..."
docker-compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml up -d

echo "[*] Waiting for database..."
sleep 15

echo "[*] Running migrations..."
docker-compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml exec -T backend alembic upgrade head

echo "[*] Seeding database (if first run)..."
docker-compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml exec -T backend python /app/scripts/seed_db.py || true

echo "[+] Deployment complete. Access KRAVIGIL at https://kravigil.yourdomain.com"
