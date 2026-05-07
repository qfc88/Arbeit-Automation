"""Shared async DB helpers for ML scripts.

Provides a thin asyncpg pool so that predict_all / auto_labeler
don't create their own psycopg2 connections.
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "job_market_data"),
            user=os.getenv("DB_USER", "jobscraper"),
            password=os.getenv("DB_PASSWORD", ""),
            min_size=1,
            max_size=5,
            command_timeout=60,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
