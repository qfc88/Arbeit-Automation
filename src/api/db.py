"""asyncpg pool shared across API routes."""

from __future__ import annotations

import os
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)


class Pool:
    """Lazy singleton wrapper around asyncpg.create_pool."""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "postgres"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "job_market_data"),
                user=os.getenv("DB_USER", "jobscraper"),
                password=os.getenv("DB_PASSWORD", ""),
                min_size=int(os.getenv("API_DB_POOL_MIN", "2")),
                max_size=int(os.getenv("API_DB_POOL_MAX", "10")),
                command_timeout=30,
            )
            logger.info("API asyncpg pool ready")
        return cls._pool

    @classmethod
    async def close(cls) -> None:
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
