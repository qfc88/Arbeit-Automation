"""Scrape control endpoints — start link scraping with dynamic filters."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import sys
from pathlib import Path

# Ensure src/ is on sys.path so we can import config.filters
_src = str(Path(__file__).resolve().parent.parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

from config.filters import ALL_FILTERS, TOP_CITIES, build_search_url

router = APIRouter(prefix="/scrape", tags=["scrape"])
logger = logging.getLogger(__name__)

# ── In-memory scrape state (single-worker MVP) ───────────────
_scrape_state: dict = {
    "running": False,
    "url": None,
    "filters": None,
    "pages_scraped": 0,
    "urls_found": 0,
    "error": None,
    "task": None,
}


# ── Request / Response models ────────────────────────────────

class ScrapeFilters(BaseModel):
    custom_url: Optional[str] = Field(None, description="Direct URL (overrides filters)")
    was: Optional[str] = Field(None, description="Keyword / job title")
    wo: Optional[str] = Field(None, description="Location (city)")
    umkreis: Optional[str] = Field(None, description="Radius km")
    arbeitszeit: Optional[list[str]] = Field(None, description="Working hours codes")
    veroeffentlichtseit: Optional[str] = Field(None, description="Published since")
    befristung: Optional[str] = Field(None, description="Contract type")
    angebotsart: Optional[str] = Field(None, description="Offer type")
    sort: Optional[str] = Field(None, description="Sort order")


class ScrapeStatus(BaseModel):
    running: bool
    url: Optional[str] = None
    filters: Optional[dict] = None
    pages_scraped: int = 0
    urls_found: int = 0
    new_urls: int = 0
    existing_urls: int = 0
    total_jobs: int = 0
    error: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────

@router.get("/filters")
async def get_filters():
    """Return available filter definitions for the FE to render."""
    return {
        "filters": ALL_FILTERS,
        "cities": TOP_CITIES,
    }


@router.post("/start")
async def start_scrape(body: ScrapeFilters):
    """Build URL from filters and launch link scraper in background."""
    global _scrape_state

    if _scrape_state["running"]:
        raise HTTPException(409, "A scrape is already running")

    filter_dict = body.model_dump(exclude_none=True)
    url = build_search_url(filter_dict)

    _scrape_state = {
        "running": True,
        "url": url,
        "filters": filter_dict,
        "pages_scraped": 0,
        "urls_found": 0,
        "new_urls": 0,
        "existing_urls": 0,
        "total_jobs": 0,
        "error": None,
        "task": None,
    }

    # Launch scraper in background
    task = asyncio.create_task(_run_scraper(url))
    _scrape_state["task"] = task
    logger.info("Scrape started: %s", url)

    return {"status": "started", "url": url}


@router.post("/stop")
async def stop_scrape():
    """Cancel a running scrape."""
    global _scrape_state
    task = _scrape_state.get("task")
    if task and not task.done():
        task.cancel()
        _scrape_state["running"] = False
        _scrape_state["error"] = "Cancelled by user"
        return {"status": "stopped"}
    return {"status": "not_running"}


@router.get("/status")
async def scrape_status():
    """Return current scrape progress."""
    return ScrapeStatus(
        running=_scrape_state["running"],
        url=_scrape_state.get("url"),
        filters=_scrape_state.get("filters"),
        pages_scraped=_scrape_state.get("pages_scraped", 0),
        urls_found=_scrape_state.get("urls_found", 0),
        new_urls=_scrape_state.get("new_urls", 0),
        existing_urls=_scrape_state.get("existing_urls", 0),
        total_jobs=_scrape_state.get("total_jobs", 0),
        error=_scrape_state.get("error"),
    )


@router.post("/preview-url")
async def preview_url(body: ScrapeFilters):
    """Return the URL that would be built from these filters (no scraping)."""
    filter_dict = body.model_dump(exclude_none=True)
    custom = filter_dict.pop("custom_url", None)
    url = custom if custom else build_search_url(filter_dict)
    return {"url": url}


@router.post("/preview")
async def preview_scrape(body: ScrapeFilters):
    """Open the search page, extract total job count, and return it.
    Also returns how many URLs already exist in the master CSV."""
    filter_dict = body.model_dump(exclude_none=True)
    custom = filter_dict.pop("custom_url", None)
    url = custom if custom else build_search_url(filter_dict)

    from scrapers.link_job import JobURLScraper
    scraper = JobURLScraper(url)

    # Get total from the page (runs headless browser briefly)
    total_jobs = await asyncio.to_thread(
        lambda: asyncio.new_event_loop().run_until_complete(scraper.get_total_job_count())
    )
    existing_count = len(scraper.get_existing_urls())

    return {
        "url": url,
        "total_jobs": total_jobs,
        "existing_urls": existing_count,
    }


# ── Background scraper runner ────────────────────────────────

async def _run_scraper(url: str):
    """Run JobURLScraper in a separate thread so time.sleep() calls
    inside the scraper don't block the main uvicorn event loop."""
    global _scrape_state
    try:
        from scrapers.link_job import JobURLScraper

        scraper = JobURLScraper(url)

        # Report existing URL count immediately
        existing_count = len(scraper.get_existing_urls())
        _scrape_state["existing_urls"] = existing_count
        _scrape_state["urls_found"] = existing_count

        # Patch save_progress to report real-time progress
        original_save_progress = scraper.save_progress

        def patched_save_progress(page_count, total_urls):
            _scrape_state["pages_scraped"] = page_count
            _scrape_state["urls_found"] = total_urls
            _scrape_state["new_urls"] = total_urls - existing_count
            original_save_progress(page_count, total_urls)

        scraper.save_progress = patched_save_progress

        # Run in a dedicated thread with its own event loop
        def _thread_target():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    scraper.scrape_all_job_urls(auto_resume=True)
                )
            finally:
                loop.close()

        job_urls = await asyncio.to_thread(_thread_target)
        df = scraper.save_job_urls_to_csv(job_urls)

        _scrape_state["running"] = False
        if df is not None:
            _scrape_state["urls_found"] = len(df)
            _scrape_state["new_urls"] = len(df) - existing_count
        logger.info("Scrape finished: %d URLs (%d new)",
                     _scrape_state["urls_found"], _scrape_state["new_urls"])

    except asyncio.CancelledError:
        _scrape_state["running"] = False
        _scrape_state["error"] = "Cancelled"
        # Save whatever was collected in temp to the main CSV
        try:
            temp_urls = scraper.load_temp_urls()
            if temp_urls:
                scraper.save_job_urls_to_csv(list(temp_urls))
                _scrape_state["urls_found"] = len(temp_urls)
                _scrape_state["new_urls"] = len(temp_urls) - existing_count
                logger.info("Scrape cancelled — saved %d URLs from temp", len(temp_urls))
            else:
                logger.info("Scrape cancelled — no temp URLs to save")
        except Exception as save_err:
            logger.warning("Failed to save temp URLs on cancel: %s", save_err)
    except Exception as exc:
        _scrape_state["running"] = False
        _scrape_state["error"] = str(exc)
        # Also try to save temp on crash
        try:
            temp_urls = scraper.load_temp_urls()
            if temp_urls:
                scraper.save_job_urls_to_csv(list(temp_urls))
                logger.info("Scrape crashed — saved %d URLs from temp", len(temp_urls))
        except Exception:
            pass
        logger.exception("Scrape failed: %s", exc)


# ══════════════════════════════════════════════════════════════
# Job Scraper (Phase 2) — scrape details, insert DB real-time
# ══════════════════════════════════════════════════════════════

_job_state: dict = {
    "running": False,
    "total": 0,
    "scraped": 0,
    "failed": 0,
    "loaded_db": 0,
    "error": None,
    "task": None,
}


class JobScrapeRequest(BaseModel):
    max_jobs: Optional[int] = Field(None, description="Max jobs to scrape (None=all)")
    resume: bool = Field(True, description="Resume from previous progress")


@router.post("/jobs/start")
async def start_job_scrape(body: JobScrapeRequest):
    """Start Phase 2: scrape job details and insert into DB in real-time."""
    global _job_state

    if _job_state["running"]:
        raise HTTPException(409, "Job scraper is already running")

    _job_state = {
        "running": True,
        "total": 0,
        "scraped": 0,
        "failed": 0,
        "loaded_db": 0,
        "error": None,
        "task": None,
    }

    task = asyncio.create_task(
        _run_job_scraper(max_jobs=body.max_jobs, resume=body.resume)
    )
    _job_state["task"] = task
    return {"status": "started"}


@router.post("/jobs/stop")
async def stop_job_scrape():
    """Cancel running job scraper."""
    global _job_state
    task = _job_state.get("task")
    if task and not task.done():
        task.cancel()
        _job_state["running"] = False
        _job_state["error"] = "Cancelled by user"
        return {"status": "stopped"}
    return {"status": "not_running"}


@router.get("/jobs/status")
async def job_scrape_status():
    """Return current job-scrape progress."""
    return {
        "running": _job_state["running"],
        "total": _job_state["total"],
        "scraped": _job_state["scraped"],
        "failed": _job_state["failed"],
        "loaded_db": _job_state["loaded_db"],
        "error": _job_state.get("error"),
    }


async def _run_job_scraper(max_jobs: int | None, resume: bool):
    """Run the job detail scraper in background, updating _job_state."""
    global _job_state
    try:
        from scrapers.job_scraper import JobScraper
        from config.settings import PATHS

        scraper = JobScraper(auto_solve_captcha=True)

        # Patch save_progress to update API state on every batch save
        _orig_save = scraper.save_progress

        async def _patched_save(batch_data, batch_number=None, **kw):
            _job_state["scraped"] = scraper.scraped_count
            _job_state["failed"] = scraper.failed_count
            result = await _orig_save(batch_data, batch_number=batch_number, **kw)
            # After save_progress completes, count DB-loaded jobs from stats
            if hasattr(scraper, "v2_stats"):
                _job_state["loaded_db"] = scraper.v2_stats.get("loaded_count", 0)
            else:
                # V1 save_progress logs "[DB] X/Y jobs loaded" — track via scraped_count minus failed
                _job_state["loaded_db"] = _job_state.get("_db_loaded", 0) + len(batch_data)
                _job_state["_db_loaded"] = _job_state["loaded_db"]
            return result

        scraper.save_progress = _patched_save

        # Also patch scrape_single_job to update progress after EVERY job
        # (not just on batch save), so FE sees real-time updates.
        _orig_scrape_single = scraper.scrape_single_job

        async def _patched_scrape_single(page, job_data, *args, **kw):
            result = await _orig_scrape_single(page, job_data, *args, **kw)
            # Update counters in real-time
            _job_state["scraped"] = scraper.scraped_count
            _job_state["failed"] = scraper.failed_count
            if hasattr(scraper, "v2_stats"):
                _job_state["loaded_db"] = scraper.v2_stats.get("loaded_count", 0)
            return result

        scraper.scrape_single_job = _patched_scrape_single

        input_csv = str(Path(PATHS["input_csv"]))

        # Load URLs to get total count
        job_urls = await scraper.load_job_urls(input_csv)
        if not job_urls:
            _job_state["running"] = False
            _job_state["error"] = "No URLs in job_urls.csv"
            return

        # Handle resume
        if resume:
            existing = await scraper.load_existing_progress()
            processed_urls = {j.get("source_url") for j in existing if j.get("source_url")}
            processed_refs = {j.get("ref_nr") for j in existing if j.get("ref_nr")}
            job_urls = [
                j for j in job_urls
                if j["job_url"] not in processed_urls
                and j.get("ref_nr") not in processed_refs
            ]

        if max_jobs and len(job_urls) > max_jobs:
            job_urls = job_urls[:max_jobs]

        _job_state["total"] = len(job_urls)

        if not job_urls:
            _job_state["running"] = False
            _job_state["error"] = "All jobs already scraped"
            return

        logger.info("Job scraper started: %d jobs", len(job_urls))

        await scraper.setup_browser()

        scraped = await scraper.process_jobs_batch(job_urls, batch_size=scraper.batch_size)

        _job_state["scraped"] = len(scraped)
        _job_state["running"] = False
        logger.info("Job scraper finished: %d scraped", len(scraped))

    except asyncio.CancelledError:
        _job_state["running"] = False
        _job_state["error"] = "Cancelled"
        logger.info("Job scraper cancelled")
    except Exception as exc:
        _job_state["running"] = False
        _job_state["error"] = str(exc)
        logger.exception("Job scraper failed: %s", exc)
