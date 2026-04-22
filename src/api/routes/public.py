"""Public (unauthenticated) endpoints — the job portal consumes these."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..db import Pool

router = APIRouter(tags=["public"])


@router.get("/jobs")
async def list_jobs(
    profession: Optional[str] = None,
    location: Optional[str] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Filterable job listing. Uses the jobs_complete view so category +
    quality columns are included for the frontend to render badges.
    """
    where: list[str] = []
    args: list = []

    if profession:
        args.append(f"%{profession}%")
        where.append(f"profession ILIKE ${len(args)}")
    if location:
        args.append(f"%{location}%")
        where.append(f"location ILIKE ${len(args)}")
    if category:
        args.append(category)
        where.append(f"predicted_category = ${len(args)}")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset = (page - 1) * limit

    pool = await Pool.get()
    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM jobs_complete {where_sql}", *args)
        rows = await conn.fetch(
            f"""
            SELECT id, profession, company_name, location, salary, job_type,
                   predicted_category, category_confidence,
                   completeness_score, scraped_at
            FROM jobs_complete
            {where_sql}
            ORDER BY scraped_at DESC NULLS LAST
            LIMIT {limit} OFFSET {offset}
            """,
            *args,
        )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [dict(r) for r in rows],
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    pool = await Pool.get()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs_complete WHERE id = $1", job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.get("/categories")
async def list_categories():
    """Return all distinct industry categories the ML service has assigned."""
    pool = await Pool.get()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT predicted_category AS name, COUNT(*) AS count
            FROM jobs
            WHERE predicted_category IS NOT NULL
            GROUP BY predicted_category
            ORDER BY count DESC
            """
        )
    return [dict(r) for r in rows]


@router.get("/health")
async def health():
    pool = await Pool.get()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ok"}
