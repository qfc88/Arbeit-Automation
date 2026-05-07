"""Analytics & statistics endpoints for the dashboard."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from fastapi import APIRouter

from ..db import Pool

router = APIRouter(prefix="/stats", tags=["stats"])


# ── Overview KPIs ──────────────────────────────────────────────

@router.get("/overview")
async def overview():
    """High-level KPI cards."""
    pool = await Pool.get()
    async with pool.acquire() as c:
        total = await c.fetchval("SELECT COUNT(*) FROM jobs")
        with_email = await c.fetchval("SELECT COUNT(*) FROM jobs WHERE email IS NOT NULL AND email != ''")
        with_phone = await c.fetchval("SELECT COUNT(*) FROM jobs WHERE telephone IS NOT NULL AND telephone != ''")
        with_desc = await c.fetchval("SELECT COUNT(*) FROM jobs WHERE job_description IS NOT NULL AND job_description != ''")
        with_category = await c.fetchval("SELECT COUNT(*) FROM jobs WHERE predicted_category IS NOT NULL")
        avg_quality = await c.fetchval("SELECT ROUND(AVG(data_quality_score)::numeric, 2) FROM jobs WHERE data_quality_score IS NOT NULL")
        companies = await c.fetchval("SELECT COUNT(DISTINCT company_name) FROM jobs WHERE company_name IS NOT NULL")
        locations = await c.fetchval("SELECT COUNT(DISTINCT location) FROM jobs WHERE location IS NOT NULL")
    return {
        "total_jobs": total,
        "with_email": with_email,
        "with_phone": with_phone,
        "with_description": with_desc,
        "with_category": with_category,
        "avg_quality_score": float(avg_quality) if avg_quality else 0,
        "unique_companies": companies,
        "unique_locations": locations,
        "email_rate": round(with_email / max(total, 1) * 100, 1),
        "phone_rate": round(with_phone / max(total, 1) * 100, 1),
        "description_rate": round(with_desc / max(total, 1) * 100, 1),
    }


# ── Location distribution ─────────────────────────────────────

@router.get("/locations")
async def locations(limit: int = 20):
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT location AS name, COUNT(*) AS count
            FROM jobs
            WHERE location IS NOT NULL AND location != ''
            GROUP BY location
            ORDER BY count DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]


# ── Job type distribution ─────────────────────────────────────

@router.get("/job-types")
async def job_types():
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT COALESCE(job_type, 'Unbekannt') AS name, COUNT(*) AS count
            FROM jobs
            GROUP BY job_type
            ORDER BY count DESC
        """)
    return [dict(r) for r in rows]


# ── ML categories distribution ────────────────────────────────

@router.get("/categories")
async def categories():
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT COALESCE(predicted_category, 'Nicht klassifiziert') AS name,
                   COUNT(*) AS count
            FROM jobs
            GROUP BY predicted_category
            ORDER BY count DESC
        """)
    return [dict(r) for r in rows]


# ── Data quality distribution ─────────────────────────────────

@router.get("/quality")
async def quality():
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT data_quality_score AS score, COUNT(*) AS count
            FROM jobs
            WHERE data_quality_score IS NOT NULL
            GROUP BY data_quality_score
            ORDER BY data_quality_score
        """)
        completeness = await c.fetch("""
            SELECT
                CASE
                    WHEN completeness_score < 0.2 THEN '0-20%'
                    WHEN completeness_score < 0.4 THEN '20-40%'
                    WHEN completeness_score < 0.6 THEN '40-60%'
                    WHEN completeness_score < 0.8 THEN '60-80%'
                    ELSE '80-100%'
                END AS bucket,
                COUNT(*) AS count
            FROM jobs_complete
            GROUP BY bucket
            ORDER BY bucket
        """)
    return {
        "quality_scores": [dict(r) for r in rows],
        "completeness": [dict(r) for r in completeness],
    }


# ── Timeline: jobs per day ────────────────────────────────────

@router.get("/timeline")
async def timeline():
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT DATE(scraped_at) AS date, COUNT(*) AS count
            FROM jobs
            WHERE scraped_at IS NOT NULL
            GROUP BY DATE(scraped_at)
            ORDER BY date
        """)
    return [{"date": r["date"].isoformat(), "count": r["count"]} for r in rows]


# ── Top companies ─────────────────────────────────────────────

@router.get("/companies")
async def top_companies(limit: int = 15):
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT company_name AS name, COUNT(*) AS count
            FROM jobs
            WHERE company_name IS NOT NULL AND company_name != ''
            GROUP BY company_name
            ORDER BY count DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]


# ── Text mining: top keywords from job descriptions ───────────

_STOP_WORDS = frozenset(
    "und der die das ein eine einen einer einem eines in von zu den für mit "
    "auf ist im sich des auch an als nicht oder aus bei nach bis über es wird "
    "sind hat dem wie wir sie ihre ihr wenn zum zur dass so kann mehr dich "
    "dein deine deinen deinem deiner uns unser unsere unseren unserem unserer "
    "ich du er sie es wir ihr sie mich mir dir ihm ihn ihnen uns euch "
    "aber noch schon sehr viel nur durch selbst unter diese diesem dieser "
    "ab am um da wo dann ob ja nein doch mal dazu dabei damit davon darauf "
    "m w d f mwd bzw ggf etc ca o o o und und die der".split()
)


@router.get("/keywords")
async def keywords(limit: int = 50):
    """Extract top keywords from job descriptions (simple TF approach)."""
    pool = await Pool.get()
    async with pool.acquire() as c:
        rows = await c.fetch("""
            SELECT job_description
            FROM jobs
            WHERE job_description IS NOT NULL AND LENGTH(job_description) > 50
            LIMIT 500
        """)

    counter: Counter = Counter()
    word_re = re.compile(r"[a-zäöüß]{4,}", re.IGNORECASE)
    for r in rows:
        words = word_re.findall(r["job_description"].lower())
        counter.update(w for w in words if w not in _STOP_WORDS and len(w) < 30)

    return [{"word": w, "count": c} for w, c in counter.most_common(limit)]


# ── Field completeness breakdown ──────────────────────────────

@router.get("/field-completeness")
async def field_completeness():
    """Per-field non-null rate for the 11 required fields."""
    fields = [
        "profession", "salary", "company_name", "location", "start_date",
        "telephone", "email", "job_description", "ref_nr",
        "external_link", "application_link",
    ]
    pool = await Pool.get()
    async with pool.acquire() as c:
        total = await c.fetchval("SELECT COUNT(*) FROM jobs")
        result = []
        for f in fields:
            cnt = await c.fetchval(
                f"SELECT COUNT(*) FROM jobs WHERE {f} IS NOT NULL AND {f} != ''"
            )
            result.append({
                "field": f,
                "count": cnt,
                "rate": round(cnt / max(total, 1) * 100, 1),
            })
    return result


# ── Scraping progress (reads from file system) ────────────────

@router.get("/scraping-progress")
async def scraping_progress():
    """
    Read current scraping session progress from the data directory.
    This enables realtime monitoring even when scraper runs on host.
    """
    output_dir = Path("data/output")
    sessions = []

    # Scan session directories
    if output_dir.exists():
        for d in sorted(output_dir.iterdir(), reverse=True):
            if d.is_dir() and d.name.startswith("scrape_session_"):
                batches = list(d.glob("scraped_jobs_batch_*.json"))
                total_jobs = 0
                for bf in batches:
                    try:
                        with open(bf) as f:
                            total_jobs += len(json.load(f))
                    except Exception:
                        pass

                progress_csv = d / "scraped_jobs_progress.csv"
                csv_lines = 0
                if progress_csv.exists():
                    csv_lines = sum(1 for _ in open(progress_csv)) - 1  # minus header

                sessions.append({
                    "session_id": d.name,
                    "batch_files": len(batches),
                    "total_jobs_in_batches": total_jobs,
                    "progress_csv_rows": max(csv_lines, 0),
                })

    # Input URLs count
    input_csv = Path("data/input/job_urls.csv")
    total_urls = 0
    if input_csv.exists():
        total_urls = sum(1 for _ in open(input_csv)) - 1

    # DB count
    pool = await Pool.get()
    async with pool.acquire() as c:
        db_count = await c.fetchval("SELECT COUNT(*) FROM jobs")

    return {
        "total_input_urls": total_urls,
        "jobs_in_database": db_count,
        "sessions": sessions,
    }
