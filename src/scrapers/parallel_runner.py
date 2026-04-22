"""
Parallel job scraping runner — producer-consumer with asyncio.

Creates N browser contexts (workers) that pull URLs from a shared queue.
A separate persistor coroutine handles batch saving without blocking scrape.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "config"))

from config.settings import SCRAPER_SETTINGS, BROWSER_SETTINGS

logger = logging.getLogger(__name__)


async def _block_assets(route):
    """Abort image/font/css/media requests to speed up page load."""
    if route.request.resource_type in ("image", "font", "stylesheet", "media"):
        await route.abort()
    else:
        await route.continue_()


async def _create_worker_context(
    browser: Browser,
    worker_id: int,
    storage_state: Optional[str] = None,
    block_assets: bool = True,
) -> BrowserContext:
    """Create isolated browser context for a worker."""
    ctx_opts = {
        "user_agent": BROWSER_SETTINGS.get("user_agent"),
        "viewport": BROWSER_SETTINGS.get("viewport", {"width": 1920, "height": 1080}),
    }
    if "timezone_id" in BROWSER_SETTINGS:
        ctx_opts["timezone_id"] = BROWSER_SETTINGS["timezone_id"]
    if "locale" in BROWSER_SETTINGS:
        ctx_opts["locale"] = BROWSER_SETTINGS["locale"]
    if storage_state:
        ctx_opts["storage_state"] = storage_state

    ctx = await browser.new_context(**ctx_opts)
    if block_assets:
        await ctx.route("**/*", _block_assets)
    logger.debug(f"Worker {worker_id}: context created")
    return ctx


async def _worker(
    worker_id: int,
    browser: Browser,
    url_queue: asyncio.Queue,
    result_queue: asyncio.Queue,
    scrape_fn,
    sem: asyncio.Semaphore,
    delay: float,
    block_assets: bool = True,
):
    """
    Worker coroutine: pulls job dicts from *url_queue*, calls *scrape_fn(page, job_data)*,
    pushes result to *result_queue*.
    """
    ctx = await _create_worker_context(browser, worker_id, block_assets=block_assets)
    page = await ctx.new_page()

    jobs_done = 0
    try:
        while True:
            try:
                job_data = url_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            async with sem:
                try:
                    result = await scrape_fn(page, job_data)
                    await result_queue.put(result)
                    jobs_done += 1
                except Exception as e:
                    logger.error(f"Worker {worker_id} failed on {job_data.get('job_url', '?')}: {e}")
                    # Push an error record so nothing is silently dropped
                    error_record = _make_error_record(job_data, e)
                    await result_queue.put(error_record)
                finally:
                    url_queue.task_done()

                if delay > 0:
                    await asyncio.sleep(delay)
    finally:
        await page.close()
        await ctx.close()
        logger.info(f"Worker {worker_id}: finished ({jobs_done} jobs)")


def _make_error_record(job_data: Dict, error: Exception) -> Dict:
    """Create a minimal error record matching the scraper output schema."""
    return {
        "profession": None,
        "salary": None,
        "company_name": None,
        "location": None,
        "start_date": None,
        "telephone": None,
        "email": None,
        "job_description": None,
        "ref_nr": job_data.get("ref_nr"),
        "external_link": None,
        "application_link": None,
        "job_type": None,
        "ausbildungsberuf": None,
        "application_method": None,
        "contact_person": None,
        "scraped_at": datetime.now().isoformat(),
        "source_url": job_data.get("job_url"),
        "error": f"Worker error: {error}",
        "captcha_solved": False,
        "is_external_redirect": False,
    }


async def run_parallel(
    job_urls: List[Dict],
    scrape_fn,
    on_batch_ready=None,
    concurrency: int = None,
    delay: float = None,
    batch_save_size: int = None,
    headless: bool = None,
    browser: Optional[Browser] = None,
):
    """
    Scrape *job_urls* in parallel using *concurrency* browser contexts.

    Parameters
    ----------
    job_urls : list[dict]
        Each dict must contain at least ``job_url`` and optionally ``ref_nr``.
    scrape_fn : async callable(page, job_data) -> dict
        The per-job scraping function (e.g. ``scraper.scrape_single_job``).
    on_batch_ready : optional async callable(list[dict], int)
        Called every *batch_save_size* results with (jobs_batch, batch_number).
    concurrency : int
        Number of parallel browser contexts.  Defaults to ``SCRAPER_SETTINGS['concurrency']``.
    delay : float
        Seconds to wait between jobs per worker.
    batch_save_size : int
        How many results to collect before calling *on_batch_ready*.
    headless : bool
        Browser headless mode. Ignored when *browser* is provided.
    browser : Browser, optional
        Reuse an existing Playwright browser (e.g. the one owned by ``JobScraper``).
        When omitted, a new browser is launched and closed here.

    Returns
    -------
    list[dict]  — all scraped job records (including error records).
    """
    concurrency = concurrency or SCRAPER_SETTINGS.get("concurrency", 6)
    delay = delay if delay is not None else SCRAPER_SETTINGS.get("delay_between_jobs", 0.5)
    batch_save_size = batch_save_size or SCRAPER_SETTINGS.get("save_every_n_jobs", 50)
    headless = headless if headless is not None else SCRAPER_SETTINGS.get("headless", True)
    block_assets = SCRAPER_SETTINGS.get("block_assets", True)

    total = len(job_urls)
    if total == 0:
        return []

    logger.info(f"Starting parallel scrape: {total} jobs, {concurrency} workers, delay={delay}s")

    url_queue: asyncio.Queue = asyncio.Queue()
    result_queue: asyncio.Queue = asyncio.Queue()
    sem = asyncio.Semaphore(concurrency)

    for jd in job_urls:
        url_queue.put_nowait(jd)

    all_results: List[Dict] = []
    batch_number = 0
    t0 = time.monotonic()

    playwright_ctx = None
    owns_browser = browser is None
    if owns_browser:
        playwright_ctx = await async_playwright().start()
        browser = await playwright_ctx.chromium.launch(
            headless=headless,
            args=BROWSER_SETTINGS.get("args", []),
        )

    try:
        workers = [
            asyncio.create_task(
                _worker(i, browser, url_queue, result_queue, scrape_fn, sem, delay, block_assets)
            )
            for i in range(min(concurrency, total))
        ]

        done_count = 0
        pending_batch: List[Dict] = []

        async def _collect():
            nonlocal done_count, batch_number, pending_batch
            while done_count < total:
                result = await result_queue.get()
                all_results.append(result)
                pending_batch.append(result)
                done_count += 1

                if done_count % 10 == 0 or done_count == total:
                    elapsed = time.monotonic() - t0
                    rate = done_count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(f"[PROGRESS] {done_count}/{total} jobs ({rate:.0f} jobs/min)")

                if on_batch_ready and len(pending_batch) >= batch_save_size:
                    batch_number += 1
                    await on_batch_ready(list(pending_batch), batch_number)
                    pending_batch.clear()

        collector = asyncio.create_task(_collect())
        await asyncio.gather(*workers)
        await collector

        if on_batch_ready and pending_batch:
            batch_number += 1
            await on_batch_ready(list(pending_batch), batch_number)
    finally:
        if owns_browser:
            await browser.close()
            if playwright_ctx:
                await playwright_ctx.stop()

    elapsed = time.monotonic() - t0
    successes = sum(1 for r in all_results if not r.get("error"))
    logger.info(
        f"Parallel scrape done: {total} jobs in {elapsed:.0f}s "
        f"({successes} ok, {total - successes} errors, "
        f"{total / max(elapsed, 0.001) * 60:.0f} jobs/min)"
    )
    return all_results
