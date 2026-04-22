"""
Thin loader around the pickled sklearn pipeline.

Designed so the service.py lifespan loads once and every request shares the
same fitted estimator — no thread-safety concerns because sklearn predict
calls are stateless after fit.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib

logger = logging.getLogger(__name__)


class Predictor:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._pipeline = None
        self._categories: list[str] = []

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model file not found at {self.model_path}. "
                "Run `python -m src.ml.trainer ...` first."
            )
        bundle = joblib.load(self.model_path)
        self._pipeline = bundle["pipeline"]
        self._categories = bundle.get("categories", [])
        logger.info("Loaded classifier from %s (%d categories)",
                    self.model_path, len(self._categories))

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def predict(self, profession: str, description: Optional[str] = None) -> dict:
        """Return {'category', 'confidence', 'top_k': [...]}"""
        if self._pipeline is None:
            raise RuntimeError("Predictor not loaded")

        text = profession or ""
        if description:
            text = f"{text}\n{description[:2000]}"

        # predict_proba is available because LogisticRegression supports it
        proba = self._pipeline.predict_proba([text])[0]
        classes = list(self._pipeline.classes_)

        ranked = sorted(zip(classes, proba), key=lambda kv: kv[1], reverse=True)
        top_label, top_conf = ranked[0]
        return {
            "category": top_label,
            "confidence": round(float(top_conf), 4),
            "top_k": [
                {"category": c, "confidence": round(float(p), 4)}
                for c, p in ranked[:3]
            ],
        }
