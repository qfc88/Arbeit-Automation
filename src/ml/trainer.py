"""
Baseline trainer: TF-IDF (char + word) + Logistic Regression.

Runs in a few minutes on CPU for ~10k samples. The Pha 3.4 plan upgrades to
fine-tuned gbert-base on the RTX 2060; until the labelled data volume
justifies that, this baseline is the default.

Usage:
    python -m src.ml.trainer \
        --data data/ml/training.jsonl \
        --out  src/ml/models/baseline.joblib
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .categories import CATEGORIES

logger = logging.getLogger(__name__)


def _iter_records(path: Path) -> Iterable[dict]:
    """Yield {text, label} dicts from a JSONL dump."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _load(path: Path) -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for rec in _iter_records(path):
        label = rec.get("label") or rec.get("category")
        text = rec.get("text") or rec.get("profession", "")
        desc = rec.get("description", "")
        if desc:
            text = f"{text}\n{desc[:2000]}"
        if not label or label not in CATEGORIES:
            continue
        texts.append(text)
        labels.append(label)
    return texts, labels


def build_pipeline() -> Pipeline:
    """Word-level TF-IDF + logistic regression. Char n-grams can be added later."""
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=50_000,
                min_df=2,
                sublinear_tf=True,
                strip_accents="unicode",
                lowercase=True,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                n_jobs=-1,
                class_weight="balanced",
                solver="saga",
                C=1.0,
            )),
        ]
    )


def train(data_path: Path, out_path: Path, test_size: float = 0.15, seed: int = 42) -> None:
    texts, labels = _load(data_path)
    if not texts:
        raise SystemExit(f"No usable rows in {data_path}")

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, stratify=labels, random_state=seed,
    )

    pipe = build_pipeline()
    logger.info("Training on %d samples, %d categories", len(X_train), len(set(labels)))
    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    report = classification_report(y_test, y_pred, digits=3)
    logger.info("Eval report:\n%s", report)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "categories": CATEGORIES}, out_path)
    logger.info("Saved model to %s", out_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Train baseline TF-IDF + LR classifier.")
    ap.add_argument("--data", type=Path, required=True, help="JSONL with {text,label}")
    ap.add_argument("--out", type=Path, required=True, help="Output .joblib path")
    args = ap.parse_args()
    train(args.data, args.out)


if __name__ == "__main__":
    main()
