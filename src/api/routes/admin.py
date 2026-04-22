"""Admin endpoints — JWT-gated, blocked at VPS nginx for defence in depth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_admin
from ..db import Pool

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CategoryOverride(BaseModel):
    corrected_category: str = Field(..., max_length=64)
    notes: str | None = None


@router.get("/sessions")
async def list_sessions(limit: int = 50):
    pool = await Pool.get()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT session_id, started_at, finished_at, total_jobs,
                   successful_jobs, failed_jobs, captchas_solved
            FROM scraping_sessions
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/quality")
async def quality_summary():
    pool = await Pool.get()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM data_quality_summary")
    return dict(row) if row else {}


@router.get("/ml/low-confidence")
async def low_confidence_jobs(limit: int = 50, threshold: float = 0.6):
    """Jobs the ML service flagged for human review."""
    pool = await Pool.get()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, profession, company_name, predicted_category,
                   category_confidence, scraped_at
            FROM jobs
            WHERE category_confidence IS NOT NULL
              AND category_confidence < $1
              AND category_source = 'ml'
            ORDER BY category_confidence ASC
            LIMIT $2
            """,
            threshold, limit,
        )
    return [dict(r) for r in rows]


@router.post("/ml/override/{job_id}")
async def override_category(
    job_id: str,
    body: CategoryOverride,
    admin: dict = Depends(require_admin),
):
    """Admin overrides the ML label; original prediction stored in ml_feedback."""
    pool = await Pool.get()
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT predicted_category, category_confidence FROM jobs WHERE id = $1",
                job_id,
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="Job not found")

            await conn.execute(
                """
                INSERT INTO ml_feedback
                    (job_id, predicted_category, predicted_confidence,
                     corrected_category, corrected_by, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                job_id,
                existing["predicted_category"],
                existing["category_confidence"],
                body.corrected_category,
                admin["sub"],
                body.notes,
            )
            await conn.execute(
                """
                UPDATE jobs
                SET predicted_category = $2,
                    category_confidence = 1.0,
                    category_source = 'human_override'
                WHERE id = $1
                """,
                job_id, body.corrected_category,
            )
    return {"status": "ok", "job_id": job_id}
