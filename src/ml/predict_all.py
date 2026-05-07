"""
Classify all jobs in the DB using the trained BERT model and update predicted_category.

Usage:
    python -m src.ml.predict_all
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .predictor import Predictor
from .db import get_pool, close_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_PATH = Path(os.getenv("ML_MODEL_PATH", "src/ml/models/gbert_category"))


async def predict_all():
    predictor = Predictor(MODEL_PATH)
    predictor.load()
    logger.info("Model type: %s", predictor.model_type)

    pool = await get_pool()

    # Get all jobs
    rows = await pool.fetch("SELECT id, profession, job_description FROM jobs")
    logger.info("Predicting categories for %d jobs...", len(rows))

    updated = 0
    for row in rows:
        result = predictor.predict(row["profession"] or "", row["job_description"])
        await pool.execute(
            """UPDATE jobs
               SET predicted_category = $1,
                   category_confidence = $2,
                   category_source = $3
               WHERE id = $4""",
            result["category"], result["confidence"], "ml", row["id"],
        )
        updated += 1

    logger.info("Updated %d jobs with predicted categories", updated)

    # Print distribution
    dist_rows = await pool.fetch("""
        SELECT predicted_category, COUNT(*) AS cnt,
               ROUND(AVG(category_confidence)::numeric, 3) AS avg_conf
        FROM jobs
        WHERE predicted_category IS NOT NULL
        GROUP BY predicted_category
        ORDER BY cnt DESC
    """)
    print("\nCategory Distribution:")
    print(f"{'Category':<20} {'Count':>6} {'Avg Conf':>10}")
    print("-" * 38)
    for r in dist_rows:
        print(f"{r['predicted_category']:<20} {r['cnt']:>6} {float(r['avg_conf']):>10.3f}")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(predict_all())


if __name__ == "__main__":
    predict_all()
