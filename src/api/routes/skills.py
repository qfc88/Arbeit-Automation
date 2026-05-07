"""Skill extraction routes: extract skills from jobs, view analytics."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_src = str(Path(__file__).resolve().parents[2])
if _src not in sys.path:
    sys.path.insert(0, _src)

from ml.skill_extractor import extract_skills, skills_to_dicts, extract_language_requirements
from ..db import Pool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["skills"])

# ── State for batch extraction ──────────────────────────────────────────────
_extract_state: dict = {"running": False, "progress": "", "error": None}


# ── Schemas ─────────────────────────────────────────────────────────────────
class ExtractRequest(BaseModel):
    profession: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=20_000)


# ── Single extraction (try-it) ──────────────────────────────────────────────
@router.post("/skills/extract")
async def extract_single(req: ExtractRequest):
    """Extract skills from a single job description (demo endpoint)."""
    skills = extract_skills(req.profession, req.description)
    languages = extract_language_requirements(req.description)
    return {
        "skills": skills_to_dicts(skills),
        "languages": languages,
        "total": len(skills),
    }


# ── Extract all jobs in DB ──────────────────────────────────────────────────
@router.post("/skills/extract-all")
async def extract_all_jobs():
    """Batch-extract skills from all jobs and persist to job_skills table."""
    if _extract_state["running"]:
        raise HTTPException(409, "Extraction already running")

    _extract_state["running"] = True
    _extract_state["progress"] = "Starting…"
    _extract_state["error"] = None

    async def _run():
        try:
            pool = await Pool.get()
            rows = await pool.fetch(
                "SELECT id, profession, job_description FROM jobs"
            )
            total = len(rows)
            _extract_state["progress"] = f"Extracting 0/{total}…"

            extracted_count = 0
            skill_count = 0

            for i, row in enumerate(rows):
                job_id = row["id"]
                skills = extract_skills(
                    row["profession"] or "",
                    row["job_description"],
                )

                if skills:
                    # Upsert skills for this job
                    await pool.execute(
                        "DELETE FROM job_skills WHERE job_id = $1", job_id
                    )
                    await pool.executemany(
                        """INSERT INTO job_skills (job_id, skill, category, mentions, context)
                           VALUES ($1, $2, $3, $4, $5)""",
                        [
                            (job_id, s.skill, s.category, s.mentions, s.context)
                            for s in skills
                        ],
                    )
                    skill_count += len(skills)
                    extracted_count += 1

                await pool.execute(
                    "UPDATE jobs SET skills_extracted = TRUE WHERE id = $1", job_id
                )

                if (i + 1) % 50 == 0 or (i + 1) == total:
                    _extract_state["progress"] = (
                        f"Extracting {i+1}/{total}… "
                        f"({extracted_count} jobs, {skill_count} skills)"
                    )

            _extract_state["progress"] = (
                f"Done! {extracted_count}/{total} jobs → {skill_count} skills extracted."
            )
        except Exception as e:
            _extract_state["error"] = str(e)
            logger.exception("extract-all failed")
        finally:
            _extract_state["running"] = False

    asyncio.create_task(_run())
    return {"message": "Extraction started"}


# ── Status ──────────────────────────────────────────────────────────────────
@router.get("/skills/extract-status")
async def extract_status():
    return _extract_state


# ── Top skills across all jobs ──────────────────────────────────────────────
@router.get("/skills/top")
async def top_skills(limit: int = 30, category: str | None = None):
    """Return the most demanded skills across all jobs."""
    pool = await Pool.get()

    if category:
        rows = await pool.fetch(
            """SELECT skill, category, COUNT(DISTINCT job_id) AS job_count,
                      SUM(mentions) AS total_mentions
               FROM job_skills
               WHERE category = $1
               GROUP BY skill, category
               ORDER BY job_count DESC
               LIMIT $2""",
            category, limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT skill, category, COUNT(DISTINCT job_id) AS job_count,
                      SUM(mentions) AS total_mentions
               FROM job_skills
               GROUP BY skill, category
               ORDER BY job_count DESC
               LIMIT $1""",
            limit,
        )

    total_jobs = await pool.fetchval(
        "SELECT COUNT(DISTINCT job_id) FROM job_skills"
    )

    return {
        "total_jobs_with_skills": total_jobs or 0,
        "skills": [
            {
                "skill": r["skill"],
                "category": r["category"],
                "job_count": r["job_count"],
                "total_mentions": r["total_mentions"],
                "pct": round(r["job_count"] / total_jobs * 100, 1) if total_jobs else 0,
            }
            for r in rows
        ],
    }


# ── Category breakdown ──────────────────────────────────────────────────────
@router.get("/skills/categories")
async def skill_categories():
    """Return skill counts grouped by category."""
    pool = await Pool.get()
    rows = await pool.fetch(
        """SELECT category,
                  COUNT(DISTINCT skill) AS unique_skills,
                  COUNT(DISTINCT job_id) AS job_count,
                  SUM(mentions) AS total_mentions
           FROM job_skills
           GROUP BY category
           ORDER BY job_count DESC"""
    )
    total_jobs = await pool.fetchval("SELECT COUNT(*) FROM jobs")
    extracted = await pool.fetchval(
        "SELECT COUNT(*) FROM jobs WHERE skills_extracted = TRUE"
    )
    total_skill_rows = await pool.fetchval("SELECT COUNT(*) FROM job_skills")

    return {
        "total_jobs": total_jobs or 0,
        "extracted": extracted or 0,
        "total_skill_entries": total_skill_rows or 0,
        "categories": [
            {
                "category": r["category"],
                "unique_skills": r["unique_skills"],
                "job_count": r["job_count"],
                "total_mentions": r["total_mentions"],
            }
            for r in rows
        ],
    }


# ── Skills for a single job ────────────────────────────────────────────────
@router.get("/skills/job/{job_id}")
async def job_skills(job_id: str):
    """Return extracted skills for a specific job."""
    pool = await Pool.get()
    rows = await pool.fetch(
        """SELECT skill, category, mentions, context
           FROM job_skills
           WHERE job_id = $1
           ORDER BY category, mentions DESC""",
        job_id,
    )
    return {
        "job_id": job_id,
        "skills": [dict(r) for r in rows],
        "total": len(rows),
    }


# ── Skill detail: which jobs require it ─────────────────────────────────────
@router.get("/skills/detail/{skill_name}")
async def skill_detail(skill_name: str, limit: int = 20):
    """Return jobs that require a specific skill."""
    pool = await Pool.get()
    rows = await pool.fetch(
        """SELECT js.job_id, js.mentions, js.context,
                  j.profession, j.company_name, j.location
           FROM job_skills js
           JOIN jobs j ON j.id = js.job_id
           WHERE js.skill = $1
           ORDER BY js.mentions DESC
           LIMIT $2""",
        skill_name, limit,
    )
    total = await pool.fetchval(
        "SELECT COUNT(*) FROM job_skills WHERE skill = $1", skill_name
    )
    return {
        "skill": skill_name,
        "total_jobs": total or 0,
        "jobs": [
            {
                "job_id": str(r["job_id"]),
                "profession": r["profession"],
                "company": r["company_name"],
                "location": r["location"],
                "mentions": r["mentions"],
                "context": r["context"],
            }
            for r in rows
        ],
    }


# ── Stats overview ──────────────────────────────────────────────────────────
@router.get("/skills/stats")
async def skills_stats():
    """Return high-level skill extraction statistics."""
    pool = await Pool.get()

    total_jobs = await pool.fetchval("SELECT COUNT(*) FROM jobs")
    extracted = await pool.fetchval(
        "SELECT COUNT(*) FROM jobs WHERE skills_extracted = TRUE"
    )
    total_skills = await pool.fetchval("SELECT COUNT(*) FROM job_skills")
    unique_skills = await pool.fetchval(
        "SELECT COUNT(DISTINCT skill) FROM job_skills"
    )
    avg_per_job = await pool.fetchval(
        """SELECT ROUND(AVG(cnt)::numeric, 1)
           FROM (SELECT COUNT(*) AS cnt FROM job_skills GROUP BY job_id) sub"""
    )

    return {
        "total_jobs": total_jobs or 0,
        "extracted": extracted or 0,
        "total_skill_entries": total_skills or 0,
        "unique_skills": unique_skills or 0,
        "avg_skills_per_job": float(avg_per_job) if avg_per_job else 0,
    }
