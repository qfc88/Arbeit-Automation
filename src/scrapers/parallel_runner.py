"""
Parallel job scraping runner — producer-consumer with asyncio.

Creates N browser contexts (workers) that pull URLs from a shared queue.
A separate persistor coroutine handles batch saving without blocking scrape.

Anti-ban / rate-limit protections:
- Adaptive delay: backs off when errors spike, speeds up when stable.
- Per-worker jitter: randomised delay so requests don't arrive in bursts.
- Global error circuit-breaker: pauses ALL workers when consecutive errors hit a threshold.
- HTTP 429 / 503 detection: triggers cooldown across all workers.
- Consecutive-error cap per worker: worker self-terminates to avoid IP-burn.
"""

import asyncio
import logging
import random
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from pathlib import Path

from config.settings import SCRAPER_SETTINGS, BROWSER_SETTINGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared adaptive-rate state (one per run_parallel call)
# ---------------------------------------------------------------------------

class _RateController:
    """Shared state that all workers consult before each request."""

    def __init__(self, base_delay: float, concurrency: int):
        self.base_delay = base_delay
        self.current_delay = base_delay
        self.concurrency = concurrency
        self._lock = asyncio.Lock()
        self._consecutive_errors = 0
        self._total_ok = 0
        self._total_err = 0
        self._cooldown_until: float = 0          # monotonic timestamp
        self._max_delay = max(base_delay * 10, 15.0)   # hard ceiling
        self._min_delay = max(base_delay * 0.5, 0.3)
        # Circuit-breaker: pause when N consecutive errors across all workers
        self._circuit_break_threshold = concurrency * 3

    async def wait(self):
        """Called by a worker before starting a new job."""
        # Honour global cooldown (e.g. after a 429)
        now = time.monotonic()
        if self._cooldown_until > now:
            wait_secs = self._cooldown_until - now
            logger.warning(f"[RATE] Global cooldown — sleeping {wait_secs:.0f}s")
            await asyncio.sleep(wait_secs)

        # Per-worker jitter: ±30 % of current_delay
        jitter = self.current_delay * random.uniform(-0.3, 0.3)
        await asyncio.sleep(max(0, self.current_delay + jitter))

    async def report_ok(self):
        async with self._lock:
            self._total_ok += 1
            self._consecutive_errors = 0
            # Ease delay back down (slowly)
            if self.current_delay > self.base_delay:
                self.current_delay = max(self._min_delay,
                                         self.current_delay * 0.92)

    async def report_error(self, error: Exception):
        async with self._lock:
            self._total_err += 1
            self._consecutive_errors += 1
            err_str = str(error).lower()

            # Rate-limit / server overload → big cooldown
            if any(code in err_str for code in ("429", "503", "too many requests",
                                                 "rate limit", "blocked")):
                cooldown = 30 + random.uniform(0, 15)
                self._cooldown_until = time.monotonic() + cooldown
                self.current_delay = min(self.current_delay * 2, self._max_delay)
                logger.warning(f"[RATE] 429/503 detected — cooldown {cooldown:.0f}s, "
                               f"delay → {self.current_delay:.1f}s")
                return

            # Network blip → moderate backoff
            if any(kw in err_str for kw in ("network", "timeout", "err_connection",
                                             "net::err")):
                self.current_delay = min(self.current_delay * 1.4, self._max_delay)
                logger.info(f"[RATE] Network error — delay → {self.current_delay:.1f}s")

            # Circuit-breaker
            if self._consecutive_errors >= self._circuit_break_threshold:
                cooldown = 60 + random.uniform(0, 30)
                self._cooldown_until = time.monotonic() + cooldown
                logger.error(f"[RATE] Circuit breaker! {self._consecutive_errors} consecutive "
                             f"errors — pausing {cooldown:.0f}s")
                self._consecutive_errors = 0  # reset after pause

    @property
    def should_stop(self) -> bool:
        """Emergency kill-switch: too many errors compared to successes."""
        total = self._total_ok + self._total_err
        if total < 20:
            return False
        return self._total_err / total > 0.8  # >80 % failure → abort


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
    rate_ctrl: Optional[_RateController] = None,
):
    """
    Worker coroutine: pulls job dicts from *url_queue*, calls *scrape_fn(page, job_data)*,
    pushes result to *result_queue*.
    
    Anti-ban protections:
    - Consults rate_ctrl before each job (adaptive delay + cooldown).
    - Self-terminates after too many consecutive worker-level errors.
    - Recreates page on crash (but not the full browser).
    """
    ctx = await _create_worker_context(browser, worker_id, block_assets=block_assets)
    page = await ctx.new_page()

    jobs_done = 0
    worker_consecutive_errors = 0
    MAX_WORKER_ERRORS = 10  # worker gives up after this many in a row

    try:
        while True:
            # Emergency: rate controller says abort
            if rate_ctrl and rate_ctrl.should_stop:
                logger.error(f"Worker {worker_id}: global error rate too high — stopping")
                break

            # Worker-level consecutive error cap
            if worker_consecutive_errors >= MAX_WORKER_ERRORS:
                logger.error(f"Worker {worker_id}: {MAX_WORKER_ERRORS} consecutive errors — stopping")
                break

            try:
                job_data = url_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            async with sem:
                # Adaptive delay before request
                if rate_ctrl:
                    await rate_ctrl.wait()

                try:
                    result = await scrape_fn(page, job_data)
                    await result_queue.put(result)
                    jobs_done += 1
                    worker_consecutive_errors = 0
                    if rate_ctrl:
                        await rate_ctrl.report_ok()
                except Exception as e:
                    err_str = str(e)
                    logger.error(f"Worker {worker_id} failed on {job_data.get('job_url', '?')}: {e}")
                    worker_consecutive_errors += 1
                    if rate_ctrl:
                        await rate_ctrl.report_error(e)

                    # Page crash → recreate page within same context
                    if "crash" in err_str.lower() or "closed" in err_str.lower():
                        try:
                            await page.close()
                        except Exception:
                            pass
                        try:
                            page = await ctx.new_page()
                            logger.info(f"Worker {worker_id}: page recreated after crash")
                        except Exception:
                            logger.error(f"Worker {worker_id}: cannot recreate page — stopping")
                            error_record = _make_error_record(job_data, e)
                            await result_queue.put(error_record)
                            url_queue.task_done()
                            break

                    error_record = _make_error_record(job_data, e)
                    await result_queue.put(error_record)
                finally:
                    url_queue.task_done()
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
    rate_ctrl = _RateController(base_delay=delay, concurrency=concurrency)

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
                _worker(i, browser, url_queue, result_queue, scrape_fn,
                        sem, delay, block_assets, rate_ctrl)
            )
            for i in range(min(concurrency, total))
        ]

        done_count = 0
        pending_batch: List[Dict] = []

        async def _collect():
            nonlocal done_count, batch_number, pending_batch
            while done_count < total:
                # Don't wait forever — workers may have stopped early
                try:
                    result = await asyncio.wait_for(result_queue.get(), timeout=120)
                except asyncio.TimeoutError:
                    # Check if all workers are done
                    if all(w.done() for w in workers):
                        logger.warning("[COLLECT] All workers finished but queue not drained — stopping")
                        break
                    continue

                all_results.append(result)
                pending_batch.append(result)
                done_count += 1

                if done_count % 10 == 0 or done_count == total:
                    elapsed = time.monotonic() - t0
                    rate = done_count / elapsed * 60 if elapsed > 0 else 0
                    logger.info(
                        f"[PROGRESS] {done_count}/{total} jobs ({rate:.0f} jobs/min) "
                        f"| delay={rate_ctrl.current_delay:.1f}s "
                        f"| ok={rate_ctrl._total_ok} err={rate_ctrl._total_err}"
                    )

                if on_batch_ready and len(pending_batch) >= batch_save_size:
                    batch_number += 1
                    await on_batch_ready(list(pending_batch), batch_number)
                    pending_batch.clear()

        collector = asyncio.create_task(_collect())
        await asyncio.gather(*workers)
        # Give collector a moment to drain remaining items
        try:
            await asyncio.wait_for(collector, timeout=30)
        except asyncio.TimeoutError:
            collector.cancel()

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
