FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY tests /app/tests
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

CMD ["celery", "-A", "app.workers.celery_app.celery_app", "worker", "--loglevel=INFO"]
