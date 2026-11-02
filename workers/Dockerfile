FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
COPY workers ./workers
RUN python -m pip install --no-cache-dir .
USER 10001:10001
CMD ["celery", "-A", "workers.celery_app", "worker", "--loglevel=INFO"]
