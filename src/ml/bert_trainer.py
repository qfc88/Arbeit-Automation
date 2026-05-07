"""
GPU-accelerated BERT trainer for job category classification.
Fine-tunes deepset/gbert-base on auto-labeled data from the DB.

Usage:
    python -m src.ml.bert_trainer \
        --data data/ml/training.jsonl \
        --out  src/ml/models/gbert_category
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from torch.utils.data import Dataset

from .categories import CATEGORIES

logger = logging.getLogger(__name__)

MODEL_NAME = "bert-base-german-cased"
MAX_LEN = 256


class JobDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=MAX_LEN,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        item = {k: v[idx] for k, v in self.encodings.items()}
        item["labels"] = self.labels[idx]
        return item


def load_data(path: Path) -> tuple[list[str], list[int]]:
    """Load JSONL, return texts and numeric labels."""
    texts, labels = [], []
    label2id = {cat: i for i, cat in enumerate(CATEGORIES)}

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            label = rec.get("label")
            if label not in label2id:
                continue
            text = rec.get("text", "")
            desc = rec.get("description", "")
            if desc:
                text = f"{text} [SEP] {desc[:800]}"
            texts.append(text)
            labels.append(label2id[label])

    return texts, labels


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    f1 = f1_score(labels, preds, average="weighted")
    return {"f1": f1}


def train(data_path: Path, out_path: Path, epochs: int = 8, batch_size: int = 16):
    logger.info("Loading data from %s", data_path)
    texts, labels = load_data(data_path)
    if not texts:
        raise SystemExit(f"No usable rows in {data_path}")

    num_labels = len(CATEGORIES)
    logger.info("Loaded %d samples, %d categories", len(texts), num_labels)

    # Split
    X_train, X_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.15, stratify=labels, random_state=42
    )
    logger.info("Train: %d, Val: %d", len(X_train), len(X_val))

    # Tokenizer + Model
    logger.info("Loading %s...", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=num_labels,
        id2label={i: cat for i, cat in enumerate(CATEGORIES)},
        label2id={cat: i for i, cat in enumerate(CATEGORIES)},
    )

    train_dataset = JobDataset(X_train, y_train, tokenizer)
    val_dataset = JobDataset(X_val, y_val, tokenizer)

    # Training args optimized for RTX 2060 12GB
    training_args = TrainingArguments(
        output_dir=str(out_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        warmup_ratio=0.1,
        weight_decay=0.01,
        learning_rate=2e-5,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        fp16=True,
        logging_steps=10,
        save_total_limit=2,
        report_to="none",
        dataloader_num_workers=2,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    logger.info("Starting training on GPU: %s", torch.cuda.get_device_name(0))
    trainer.train()

    # Eval
    results = trainer.evaluate()
    logger.info("Final eval F1: %.4f", results.get("eval_f1", 0))

    # Detailed report
    preds = trainer.predict(val_dataset)
    y_pred = np.argmax(preds.predictions, axis=-1)
    report = classification_report(
        y_val, y_pred,
        target_names=[CATEGORIES[i] for i in sorted(set(y_val))],
        digits=3,
    )
    logger.info("Classification Report:\n%s", report)

    # Save
    out_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_path)
    tokenizer.save_pretrained(out_path)

    # Also save as joblib for compatibility with existing predictor
    import joblib
    joblib.dump({
        "model_type": "gbert",
        "model_path": str(out_path),
        "categories": CATEGORIES,
        "f1_score": results.get("eval_f1", 0),
    }, out_path / "model_info.joblib")

    logger.info("Model saved to %s", out_path)
    return results


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Fine-tune gbert-base for job classification")
    ap.add_argument("--data", type=Path, default=Path("data/ml/training.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("src/ml/models/gbert_category"))
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch-size", type=int, default=16)
    args = ap.parse_args()
    train(args.data, args.out, args.epochs, args.batch_size)


if __name__ == "__main__":
    main()
