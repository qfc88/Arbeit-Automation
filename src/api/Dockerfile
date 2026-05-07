FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install API deps + ML inference deps (sklearn, torch CPU for predict)
COPY src/api/requirements.txt /app/requirements-api.txt
COPY src/ml/requirements.txt  /app/requirements-ml.txt
RUN pip install --no-cache-dir \
        -r /app/requirements-api.txt \
        -r /app/requirements-ml.txt \
        psycopg2-binary>=2.9 \
        torch --index-url https://download.pytorch.org/whl/cpu \
        transformers sentencepiece

# Copy all source modules the API routes import
COPY src/__init__.py      /app/src/__init__.py
COPY src/api              /app/src/api
COPY src/config           /app/src/config
COPY src/database         /app/src/database
COPY src/models           /app/src/models
COPY src/ml               /app/src/ml
COPY src/scrapers         /app/src/scrapers
COPY src/utils            /app/src/utils

# Pre-copy trained model if present
COPY src/ml/models        /app/src/ml/models

EXPOSE 8001
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
