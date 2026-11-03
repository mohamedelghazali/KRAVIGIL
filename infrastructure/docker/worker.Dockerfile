FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/projectdiscovery/nuclei/releases/download/v3.11.1/nuclei_3.11.1_linux_amd64.zip \
    && unzip nuclei_3.11.1_linux_amd64.zip -d /usr/local/bin/ \
    && rm nuclei_3.11.1_linux_amd64.zip \
    && chmod +x /usr/local/bin/nuclei

RUN python -m venv /opt/semgrep \
    && /opt/semgrep/bin/pip install --no-cache-dir semgrep==1.183.0 \
    && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep

# Keep Prowler's large provider SDK dependency graph isolated from the API/worker runtime.
RUN python -m venv /opt/prowler \
    && /opt/prowler/bin/pip install --no-cache-dir prowler==5.47.0 \
    && ln -s /opt/prowler/bin/prowler /usr/local/bin/prowler

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY engines/ /app/engines/
COPY workers/ /app/workers/
COPY shared/ /app/shared/
COPY ai/ /app/ai/
RUN python -m grpc_tools.protoc -I /app/shared/protocols --python_out=/app/shared/protocols --grpc_python_out=/app/shared/protocols /app/shared/protocols/network_engine.proto

RUN useradd -m -r -s /bin/bash kravigil && chown -R kravigil:kravigil /app
USER kravigil

ENV PYTHONPATH=/app:/app/shared/protocols

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
