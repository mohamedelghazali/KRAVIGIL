FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/projectdiscovery/nuclei/releases/download/v3.1.0/nuclei_3.1.0_linux_amd64.zip \
    && unzip nuclei_3.1.0_linux_amd64.zip -d /usr/local/bin/ \
    && rm nuclei_3.1.0_linux_amd64.zip \
    && chmod +x /usr/local/bin/nuclei

RUN pip install semgrep==1.53.0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY workers/ /app/workers/
COPY shared/ /app/shared/
COPY ai/ /app/ai/

RUN useradd -m -r -s /bin/bash kravigil && chown -R kravigil:kravigil /app
USER kravigil

ENV PYTHONPATH=/app

CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
