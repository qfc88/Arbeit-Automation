#
# ML inference image with BERT + GPU support.
#
# Build variants:
#   CPU only:  docker build --build-arg BASE=python:3.12-slim -f src/ml/Dockerfile .
#   GPU/CUDA:  docker build --build-arg BASE=nvidia/cuda:12.4.1-runtime-ubuntu22.04 -f src/ml/Dockerfile .
#
ARG BASE=python:3.12-slim
FROM ${BASE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# For CUDA base image, install python
RUN if ! command -v python3 &>/dev/null; then \
        apt-get update && apt-get install -y --no-install-recommends \
            python3 python3-pip python3-venv && \
        ln -sf /usr/bin/python3 /usr/bin/python && \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

COPY src/ml/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124 \
       transformers sentencepiece accelerate

COPY src/ml /app/src/ml
RUN mkdir -p /app/src && touch /app/src/__init__.py

# Pre-copy trained BERT model
COPY src/ml/models /app/src/ml/models

EXPOSE 8002
CMD ["uvicorn", "src.ml.service:app", "--host", "0.0.0.0", "--port", "8002"]
