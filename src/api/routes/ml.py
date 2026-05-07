"""ML classification routes: classify single job, batch re-classify, retrain."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Ensure src/ is on path for ml imports
_src = str(Path(__file__).resolve().parents[2])
if _src not in sys.path:
    sys.path.insert(0, _src)

from ml.predictor import Predictor
from ml.categories import CATEGORIES
from ..db import Pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ml"])

MODEL_PATH = Path(os.getenv("ML_MODEL_PATH", "src/ml/models/gbert_category"))

# Lazy-loaded predictor
_predictor: Predictor | None = None


def _get_predictor() -> Predictor:
    global _predictor
    if _predictor is None or not _predictor.loaded:
        _predictor = Predictor(MODEL_PATH)
        try:
            _predictor.load()
        except FileNotFoundError:
            raise HTTPException(503, "ML model not found. Train one first.")
    return _predictor


# ---------- schemas ----------

class ClassifyRequest(BaseModel):
    profession: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=20_000)


class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    top_k: list[dict]


class TrainStatus(BaseModel):
    running: bool = False
    progress: str = ""
    error: str | None = None


_train_state: dict = {"running": False, "progress": "", "error": None}


# ---------- endpoints ----------

@router.get("/ml/categories")
async def get_categories():
    """Return the list of supported categories."""
    return {"categories": CATEGORIES}


@router.post("/ml/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    """Classify a single job."""
    predictor = _get_predictor()
    result = predictor.predict(req.profession, req.description)
    return result


@router.get("/ml/model-info")
async def model_info():
    """Return info about the loaded model."""
    try:
        predictor = _get_predictor()
        return {
            "loaded": predictor.loaded,
            "model_type": predictor.model_type,
            "model_path": str(MODEL_PATH),
            "categories": CATEGORIES,
            "num_categories": len(CATEGORIES),
        }
    except HTTPException:
        return {
            "loaded": False,
            "model_type": "none",
            "model_path": str(MODEL_PATH),
            "categories": CATEGORIES,
            "num_categories": len(CATEGORIES),
        }


@router.post("/ml/predict-all")
async def predict_all_jobs():
    """Run prediction on all jobs in DB and update predicted_category."""
    if _train_state["running"]:
        raise HTTPException(409, "Training or prediction already running")

    _train_state["running"] = True
    _train_state["progress"] = "Starting..."
    _train_state["error"] = None

    async def _run():
        try:
            predictor = _get_predictor()
            pool = await Pool.get()

            rows = await pool.fetch(
                "SELECT id, profession, job_description FROM jobs"
            )
            total = len(rows)
            _train_state["progress"] = f"Predicting 0/{total}..."

            for i, row in enumerate(rows):
                result = predictor.predict(row["profession"] or "", row["job_description"])
                await pool.execute(
                    """UPDATE jobs
                       SET predicted_category = $1,
                           category_confidence = $2,
                           category_source = 'ml'
                       WHERE id = $3""",
                    result["category"],
                    result["confidence"],
                    row["id"],
                )
                if (i + 1) % 50 == 0:
                    _train_state["progress"] = f"Predicting {i+1}/{total}..."

            _train_state["progress"] = f"Done! {total} jobs classified."
        except Exception as e:
            _train_state["error"] = str(e)
            logger.exception("predict-all failed")
        finally:
            _train_state["running"] = False

    asyncio.create_task(_run())
    return {"message": "Prediction started", "total_jobs": "check /ml/predict-status"}


@router.get("/ml/predict-status")
async def predict_status():
    return _train_state


@router.post("/ml/retrain")
async def retrain():
    """Retrain the model from DB data."""
    if _train_state["running"]:
        raise HTTPException(409, "Already running")

    _train_state["running"] = True
    _train_state["progress"] = "Generating training data..."
    _train_state["error"] = None

    async def _run():
        try:
            from ml.auto_labeler import generate_training_data
            n = await generate_training_data()
            _train_state["progress"] = f"Labeled {n} samples. Training BERT..."

            from ml.bert_trainer import train as bert_train
            out_path = Path("src/ml/models/gbert_category")
            data_path = Path("data/ml/training.jsonl")
            await asyncio.to_thread(bert_train, data_path, out_path, 8, 16)

            # Reload predictor
            global _predictor
            _predictor = Predictor(MODEL_PATH)
            _predictor.load()

            _train_state["progress"] = "Training complete! Model reloaded."
        except Exception as e:
            _train_state["error"] = str(e)
            logger.exception("retrain failed")
        finally:
            _train_state["running"] = False

    asyncio.create_task(_run())
    return {"message": "Retraining started"}


@router.get("/ml/stats")
async def ml_stats():
    """Return category distribution from DB."""
    pool = await Pool.get()
    rows = await pool.fetch("""
        SELECT predicted_category, COUNT(*) as count,
               ROUND(AVG(category_confidence)::numeric, 3) as avg_conf
        FROM jobs
        WHERE predicted_category IS NOT NULL
        GROUP BY predicted_category
        ORDER BY count DESC
    """)
    total = await pool.fetchval("SELECT COUNT(*) FROM jobs")
    classified = await pool.fetchval(
        "SELECT COUNT(*) FROM jobs WHERE predicted_category IS NOT NULL"
    )
    return {
        "total_jobs": total,
        "classified": classified,
        "categories": [
            {
                "name": r["predicted_category"],
                "count": r["count"],
                "avg_confidence": float(r["avg_conf"]),
            }
            for r in rows
        ],
    }
