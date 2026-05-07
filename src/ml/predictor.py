"""
Predictor: supports both sklearn pipeline (.joblib) and BERT model (directory).

Loads once at startup. Thread-safe for predict calls.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

logger = logging.getLogger(__name__)


class Predictor:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._pipeline = None  # sklearn
        self._bert_model = None
        self._bert_tokenizer = None
        self._categories: list[str] = []
        self._model_type: str = "unknown"

    def load(self) -> None:
        # BERT model (directory with config.json)
        if self.model_path.is_dir() and (self.model_path / "config.json").exists():
            self._load_bert()
        # sklearn joblib
        elif self.model_path.exists() and self.model_path.suffix == ".joblib":
            self._load_sklearn()
        else:
            raise FileNotFoundError(
                f"Model not found at {self.model_path}. "
                "Run trainer first."
            )

    def _load_sklearn(self) -> None:
        bundle = joblib.load(self.model_path)
        self._pipeline = bundle["pipeline"]
        self._categories = bundle.get("categories", [])
        self._model_type = "sklearn"
        logger.info("Loaded sklearn classifier from %s (%d categories)",
                    self.model_path, len(self._categories))

    def _load_bert(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._bert_tokenizer = AutoTokenizer.from_pretrained(str(self.model_path))
        self._bert_model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_path)
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._bert_model.to(device)
        self._bert_model.eval()

        # Load categories from model_info.joblib or model config
        info_path = self.model_path / "model_info.joblib"
        if info_path.exists():
            info = joblib.load(info_path)
            self._categories = info.get("categories", [])
        else:
            config = self._bert_model.config
            self._categories = [config.id2label[i] for i in range(config.num_labels)]

        self._model_type = "gbert"
        logger.info("Loaded BERT classifier from %s (%d categories, device=%s)",
                    self.model_path, len(self._categories), device)

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None or self._bert_model is not None

    @property
    def model_type(self) -> str:
        return self._model_type

    def predict(self, profession: str, description: Optional[str] = None) -> dict:
        """Return {'category', 'confidence', 'top_k': [...]}"""
        if not self.loaded:
            raise RuntimeError("Predictor not loaded")

        if self._model_type == "gbert":
            return self._predict_bert(profession, description)
        return self._predict_sklearn(profession, description)

    def _predict_sklearn(self, profession: str, description: Optional[str] = None) -> dict:
        text = profession or ""
        if description:
            text = f"{text}\n{description[:2000]}"

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

    def _predict_bert(self, profession: str, description: Optional[str] = None) -> dict:
        import torch

        text = profession or ""
        if description:
            text = f"{text} [SEP] {description[:800]}"

        device = next(self._bert_model.parameters()).device
        inputs = self._bert_tokenizer(
            text, truncation=True, padding="max_length",
            max_length=256, return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            logits = self._bert_model(**inputs).logits[0]
            proba = torch.softmax(logits, dim=-1).cpu().numpy()

        ranked = sorted(
            zip(self._categories, proba.tolist()),
            key=lambda kv: kv[1], reverse=True
        )
        top_label, top_conf = ranked[0]
        return {
            "category": top_label,
            "confidence": round(float(top_conf), 4),
            "top_k": [
                {"category": c, "confidence": round(float(p), 4)}
                for c, p in ranked[:3]
            ],
        }
