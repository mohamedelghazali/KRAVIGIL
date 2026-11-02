FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ /app/agents/
COPY shared/ /app/shared/

RUN useradd -m -r -s /bin/bash kravigil && chown -R kravigil:kravigil /app
USER kravigil

ENV PYTHONPATH=/app

CMD ["python", "-m", "agents.runner"]
