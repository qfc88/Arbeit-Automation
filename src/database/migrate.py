"""
Database migration runner.

Applies SQL migration files in order, tracking which have already been applied
in a `schema_migrations` table.

Usage:
    # Apply all pending migrations
    python -m database.migrate

    # Show status only
    python -m database.migrate --status
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
from pathlib import Path

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Pattern: NNN_description.sql
_MIGRATION_RE = re.compile(r"^(\d{3})_.+\.sql$")


async def _get_connection() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "job_market_data"),
        user=os.getenv("DB_USER", "jobscraper"),
        password=os.getenv("DB_PASSWORD", ""),
    )


async def _ensure_tracking_table(conn: asyncpg.Connection) -> None:
    """Create the tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version   VARCHAR(10) PRIMARY KEY,
            filename  VARCHAR(255) NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _discover_migrations() -> list[tuple[str, Path]]:
    """Return sorted list of (version, path) for all migration files."""
    if not MIGRATIONS_DIR.is_dir():
        return []
    results = []
    for f in sorted(MIGRATIONS_DIR.iterdir()):
        m = _MIGRATION_RE.match(f.name)
        if m and f.suffix == ".sql":
            results.append((m.group(1), f))
    return results


async def get_applied(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


async def apply_migrations(dry_run: bool = False) -> int:
    conn = await _get_connection()
    try:
        await _ensure_tracking_table(conn)
        applied = await get_applied(conn)
        migrations = _discover_migrations()
        pending = [(v, p) for v, p in migrations if v not in applied]

        if not pending:
            logger.info("No pending migrations.")
            return 0

        for version, path in pending:
            sql = path.read_text(encoding="utf-8")
            if dry_run:
                logger.info("[DRY-RUN] Would apply %s (%s)", version, path.name)
                continue

            logger.info("Applying migration %s: %s", version, path.name)
            # Run migration in a transaction (file may have its own BEGIN/COMMIT;
            # we strip those and wrap in our own to guarantee atomicity)
            clean_sql = sql
            for token in ("BEGIN;", "COMMIT;", "BEGIN", "COMMIT"):
                clean_sql = clean_sql.replace(token, "")

            async with conn.transaction():
                await conn.execute(clean_sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                    version, path.name,
                )
            logger.info("  ✓ %s applied", path.name)

        applied_count = len(pending) if not dry_run else 0
        logger.info("Applied %d migration(s).", applied_count)
        return applied_count
    finally:
        await conn.close()


async def show_status() -> None:
    conn = await _get_connection()
    try:
        await _ensure_tracking_table(conn)
        applied = await get_applied(conn)
        migrations = _discover_migrations()

        print(f"\n{'Version':<10} {'File':<40} {'Status'}")
        print("-" * 60)
        for version, path in migrations:
            status = "applied" if version in applied else "PENDING"
            print(f"{version:<10} {path.name:<40} {status}")

        if not migrations:
            print("(no migration files found)")
        print()
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be applied")
    args = parser.parse_args()

    if args.status:
        asyncio.run(show_status())
    else:
        asyncio.run(apply_migrations(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
