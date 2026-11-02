#!/bin/bash

set -e

echo "[*] Starting KRAVIGIL E2E Playbook..."

echo "[*] 1. Building and starting infrastructure..."
docker-compose -f infrastructure/docker-compose.yml up -d --build

echo "[*] 2. Waiting for services to be healthy..."
sleep 15

echo "[*] 3. Running migrations..."
docker-compose exec -T backend alembic upgrade head

echo "[*] 4. Seeding database..."
docker-compose exec -T backend python /app/scripts/seed_db.py

echo "[*] 5. Running API Security & E2E Tests..."
pytest tests/e2e tests/integration -v

echo "[*] 6. Testing Network Engine via gRPC..."
docker-compose exec -T worker python -c "
from engines.network_cpp.grpc_client import NetworkEngineClient
client = NetworkEngineClient(host='network_engine', port=50051)
try:
    list(client.start_scan('e2e-scan', '127.0.0.1', [22]))
    print('gRPC Engine OK')
except Exception as e:
    print(f'gRPC Engine FAILED: {e}')
    exit(1)
"

echo "[+] E2E Playbook completed successfully!"
