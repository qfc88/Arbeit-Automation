#!/usr/bin/env bash
#
# Start the full job-portal stack on localhost.
#
# Usage:  ./start_local.sh [phase]
#   phase = all    → start everything (default)
#   phase = db     → PostgreSQL + Adminer only
#   phase = portal → API + Frontend + ML (assumes DB is up)
#   phase = scrape → run scraper once (assumes DB is up)
#   phase = stop   → stop all services
#   phase = load   → load scraped JSON data into DB
#   phase = train  → train ML model from DB data
#   phase = status → show service status
#
set -euo pipefail
cd "$(dirname "$0")"

# ── Env defaults ──────────────────────────────────────────────
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-!@#\$%^Qwerty1234}"
export API_JWT_SECRET="${API_JWT_SECRET:-devsecret_change_me}"
export ML_RELOAD_TOKEN="${ML_RELOAD_TOKEN:-localdev}"
export TWOCAPTCHA_API_KEY="${TWOCAPTCHA_API_KEY:-}"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.local.yml"
PHASE="${1:-all}"

log() { echo -e "\033[1;36m▶ $*\033[0m"; }
warn() { echo -e "\033[1;33m⚠ $*\033[0m"; }

case "$PHASE" in

  db)
    log "Starting PostgreSQL + Adminer..."
    $COMPOSE up -d postgres adminer
    log "DB ready at localhost:5432 | Adminer at http://localhost:8080"
    ;;

  portal)
    log "Starting API + Frontend + ML..."
    $COMPOSE up -d api frontend ml-inference
    log "Frontend: http://localhost:3000"
    log "API docs: http://localhost:8001/docs"
    log "ML health: http://localhost:8002/health"
    ;;

  scrape)
    log "Running scraper (one session)..."
    $COMPOSE run --rm job-scraper python scripts/run_automated_pipeline.py
    ;;

  load)
    log "Loading scraped data into DB..."
    $COMPOSE run --rm job-scraper python tools/simple_load.py
    ;;

  train)
    log "Generating training data from DB and training ML model..."
    $COMPOSE run --rm api python -c "
import asyncio, json, sys
sys.path.insert(0, '/app/src')
from api.db import Pool

async def export_training():
    pool = await Pool.get()
    rows = await pool.fetch('''
        SELECT profession, job_description, predicted_category
        FROM jobs
        WHERE profession IS NOT NULL
          AND job_description IS NOT NULL
        LIMIT 10000
    ''')
    if not rows:
        print('No data in DB yet. Run load first.', file=sys.stderr)
        return
    with open('/app/data/ml/training.jsonl', 'w') as f:
        for r in rows:
            cat = r['predicted_category'] or 'Other'
            obj = {'profession': r['profession'], 'description': r['job_description'][:2000], 'category': cat}
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    print(f'Exported {len(rows)} training samples to /app/data/ml/training.jsonl')

asyncio.run(export_training())
"
    $COMPOSE run --rm ml-inference python -m src.ml.trainer \
        --data /app/data/ml/training.jsonl \
        --out /app/data/ml/baseline.joblib
    # Hot-reload model
    curl -s -X POST http://localhost:8002/reload \
        -H "Authorization: Bearer $ML_RELOAD_TOKEN" && echo " Model reloaded" || warn "ML reload failed"
    ;;

  stop)
    log "Stopping all services..."
    $COMPOSE down
    ;;

  status)
    $COMPOSE ps
    echo ""
    log "Checking service health..."
    for svc in "DB:localhost:5432" "API:localhost:8001/api/health" "Frontend:localhost:3000" "ML:localhost:8002/health" "Adminer:localhost:8080" "Monitor:localhost:9002"; do
      name="${svc%%:*}"
      url="${svc#*:}"
      if [[ "$name" == "DB" ]]; then
        pg_isready -h localhost -p 5432 -U jobscraper -q 2>/dev/null && echo "  ✅ $name" || echo "  ❌ $name"
      else
        curl -sf "http://$url" >/dev/null 2>&1 && echo "  ✅ $name" || echo "  ❌ $name"
      fi
    done
    ;;

  all)
    log "Starting full stack on localhost..."
    $COMPOSE up -d
    echo ""
    log "All services starting. Wait ~30s for builds, then:"
    echo "  Frontend:  http://localhost:3000"
    echo "  API docs:  http://localhost:8001/docs"
    echo "  Adminer:   http://localhost:8080"
    echo "  Monitor:   http://localhost:9002"
    echo "  ML health: http://localhost:8002/health"
    echo ""
    warn "ML service starts in degraded mode (no model yet)."
    warn "Run './start_local.sh load' then './start_local.sh train' after scraping."
    ;;

  *)
    echo "Usage: $0 {all|db|portal|scrape|load|train|stop|status}"
    exit 1
    ;;
esac
