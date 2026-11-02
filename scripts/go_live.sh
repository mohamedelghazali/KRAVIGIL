#!/bin/bash

set -e

echo "===================================================="
echo "      KRAVIGIL Core - Full System Bootstrapping     "
echo "===================================================="

if [ ! -f .env ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
    echo "[!] Please edit .env and set secure secrets before production use."
fi

echo "[*] 1. Building Docker images..."
docker-compose -f infrastructure/docker-compose.yml build

echo "[*] 2. Starting infrastructure (DB, Redis, MinIO)..."
docker-compose -f infrastructure/docker-compose.yml up -d db redis minio target-minio

echo "[*] 3. Waiting for services to be healthy..."
sleep 15

echo "[*] 4. Starting Backend & Network Engine..."
docker-compose -f infrastructure/docker-compose.yml up -d network_engine backend

echo "[*] 5. Waiting for API to be ready..."
sleep 5

echo "[*] 6. Running database migrations..."
docker-compose exec -T backend alembic upgrade head

echo "[*] 7. Seeding database with initial admin..."
docker-compose exec -T backend python /app/scripts/seed_db.py

echo "[*] 8. Starting Workers, Frontend, and Nginx..."
docker-compose -f infrastructure/docker-compose.yml up -d worker frontend nginx

echo "[*] 9. Configuring MinIO Replication..."
set -a && . ./.env && set +a && ./infrastructure/minio/replicate.sh

echo "[*] 10. Running final health check..."
sleep 5
curl -s http://localhost/api/v1/system/health | grep -q '"status":"ok"' && echo "[+] System is healthy!" || echo "[-] System health check failed. Check logs."

echo "===================================================="
echo " [+] KRAVIGIL is LIVE at http://localhost"
echo " [+] Admin: ${ADMIN_EMAIL:-admin@kravigil.local}"
echo " [+] Password: ${ADMIN_PASSWORD:-AdminPassword123!}"
echo "===================================================="
