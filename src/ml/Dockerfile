#
# Baseline ML image (CPU only).
#
# The GPU / BERT image is a separate Dockerfile added when Pha 3.4 step 3
# lands; for now the baseline TF-IDF pipeline doesn't need CUDA so we stay
# on the slim python base to keep the image small.
#
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY src/ml/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ml /app/src/ml
RUN mkdir -p /app/src && touch /app/src/__init__.py

EXPOSE 8002
CMD ["uvicorn", "src.ml.service:app", "--host", "0.0.0.0", "--port", "8002"]
