FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir minio==7.2.20

WORKDIR /opt/kravigil-backup
COPY infrastructure/backup/pg_backup.py /opt/kravigil-backup/pg_backup.py
COPY infrastructure/backup/pg_restore.py /opt/kravigil-backup/pg_restore.py
RUN useradd --system --create-home --shell /usr/sbin/nologin kravigil-backup \
    && chown -R kravigil-backup:kravigil-backup /opt/kravigil-backup
USER kravigil-backup

CMD ["sh", "-c", "while true; do python /opt/kravigil-backup/pg_backup.py || echo 'KRAVIGIL backup failed; retrying at next interval' >&2; sleep ${BACKUP_INTERVAL_SECONDS:-86400}; done"]
