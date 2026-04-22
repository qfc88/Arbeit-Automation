# Database migrations

Forward-only SQL migrations, applied in numeric order.

## Apply

```bash
# Against the live Docker postgres
docker compose exec -T postgres psql -U jobscraper -d job_market_data \
    < src/database/migrations/001_ml_categorization.sql
```

Each migration is wrapped in `BEGIN; ... COMMIT;` and uses `IF NOT EXISTS`
so re-running is safe. There is no down-migration — if you need to undo,
write a new numbered migration.

## Convention

- `NNN_snake_case_name.sql` — three-digit zero-padded prefix.
- Top comment block explains the *why* (what feature it enables).
- Touch `schema.sql` only for fresh installs; migrations are the source of
  truth for upgrading an existing DB.
