"""
ML classification microservice (FastAPI).

Run with:
    uvicorn src.ml.service:app --host 0.0.0.0 --port 8002

Loads the trained model once at startup. If the model file is missing the
service starts in degraded mode: /classify returns 503 until /reload is
called. This lets the stack boot before the first training run.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .predictor import Predictor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = Path(os.getenv("ML_MODEL_PATH", "src/ml/models/baseline.joblib"))
RELOAD_TOKEN = os.getenv("ML_RELOAD_TOKEN")  # opt-in; /reload disabled if unset

predictor = Predictor(MODEL_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        predictor.load()
    except FileNotFoundError as e:
        logger.warning("Starting in degraded mode: %s", e)
    yield


app = FastAPI(title="Deutsch DE ML classifier", version="0.1.0", lifespan=lifespan)


class ClassifyRequest(BaseModel):
    profession: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=20_000)


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not predictor.loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded — train one and call /reload",
        )
    return predictor.predict(req.profession, req.description)


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": predictor.loaded}


_bearer = HTTPBearer(auto_error=False)


@app.post("/reload")
async def reload_model(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Reload the model file — used after an offline retraining run."""
    if not RELOAD_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ML_RELOAD_TOKEN not configured",
        )
    if creds is None or creds.credentials != RELOAD_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid reload token",
        )
    predictor.load()
    return {"status": "ok"}
