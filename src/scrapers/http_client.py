"""
Async HTTP client for arbeitsagentur.de JSON API.

Replaces Playwright-based link collection with direct API calls.
The Jobsuche API returns structured JSON — much faster than rendering HTML pages.

Usage:
    urls = await fetch_job_urls_api(search_params, max_results=1000)
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)

# Arbeitsagentur Jobsuche API base
API_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"

# Default headers mimicking browser requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "de-DE,de;q=0.9",
    "Origin": "https://www.arbeitsagentur.de",
    "Referer": "https://www.arbeitsagentur.de/jobsuche/",
}

# OAuth token endpoint for API auth
TOKEN_URL = "https://rest.arbeitsagentur.de/oauth/gettoken_cc"
CLIENT_ID = "c003a37f-024f-462a-b36d-b001be4cd24a"
CLIENT_SECRET = "32a39620-32b3-4307-9aa1-511e3d7f48a8"


async def _get_oauth_token(client: "httpx.AsyncClient") -> str:
    """Obtain OAuth bearer token for the Jobsuche API."""
    resp = await client.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    logger.debug("OAuth token obtained")
    return token


async def fetch_job_urls_api(
    was: str = "",
    wo: str = "",
    page_size: int = 100,
    max_results: int = 1000,
    angebotsart: int = 1,
) -> List[Dict[str, str]]:
    """
    Fetch job URLs from the Arbeitsagentur REST API.

    Parameters
    ----------
    was : str
        Search keyword (profession / job title).
    wo : str
        Location search.
    page_size : int
        Results per API page (max 100).
    max_results : int
        Stop after collecting this many URLs.
    angebotsart : int
        1 = Arbeit, 2 = Selbstständigkeit, 4 = Ausbildung.

    Returns
    -------
    list[dict]
        Each dict has ``job_url`` and ``ref_nr`` keys.
    """
    if not HTTPX_AVAILABLE:
        raise ImportError("httpx is required for API-based link collection. pip install httpx")

    all_urls: List[Dict[str, str]] = []

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        token = await _get_oauth_token(client)
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": f"Bearer {token}",
        }

        page = 0
        while len(all_urls) < max_results:
            params = {
                "angebotsart": angebotsart,
                "page": page,
                "size": min(page_size, max_results - len(all_urls)),
                "pav": "false",
            }
            if was:
                params["was"] = was
            if wo:
                params["wo"] = wo

            try:
                resp = await client.get(API_BASE, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Token expired, refresh
                    logger.info("Token expired, refreshing...")
                    token = await _get_oauth_token(client)
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                logger.error(f"API error on page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Request failed on page {page}: {e}")
                break

            stellenangebote = data.get("stellenangebote", [])
            if not stellenangebote:
                logger.info(f"No more results at page {page}")
                break

            for job in stellenangebote:
                ref_nr = job.get("refnr", "")
                job_url = f"https://www.arbeitsagentur.de/jobsuche/suche?id={ref_nr}&angebotsart={angebotsart}"
                all_urls.append({"job_url": job_url, "ref_nr": ref_nr})

            total_api = data.get("maxErgebnisse", 0)
            logger.info(f"Page {page}: got {len(stellenangebote)} jobs (total available: {total_api}, collected: {len(all_urls)})")

            if len(stellenangebote) < page_size:
                break
            page += 1

            # Small delay to be polite
            await asyncio.sleep(0.3)

    logger.info(f"API link collection done: {len(all_urls)} job URLs")
    return all_urls[:max_results]
