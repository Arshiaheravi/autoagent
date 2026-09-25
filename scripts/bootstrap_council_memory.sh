#!/usr/bin/env bash
# Bootstrap the council memory DB on the existing redhunter-memory-pg container.
# Idempotent — safe to re-run.
set -euo pipefail

CONTAINER="${COUNCIL_MEMORY_CONTAINER:-redhunter-memory-pg}"
PG_USER="${COUNCIL_MEMORY_PG_USER:-redhunter}"
DB_NAME="${COUNCIL_MEMORY_DB:-autoagency_memory}"
MIGRATION="$(cd "$(dirname "$0")/.." && pwd)/migrations/001_council_memory.sql"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "[bootstrap] container '${CONTAINER}' not running" >&2
    exit 1
fi

if ! [ -f "$MIGRATION" ]; then
    echo "[bootstrap] missing migration: $MIGRATION" >&2
    exit 1
fi

if docker exec "$CONTAINER" psql -U "$PG_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo "[bootstrap] db '${DB_NAME}' already exists"
else
    echo "[bootstrap] creating db '${DB_NAME}'..."
    docker exec "$CONTAINER" createdb -U "$PG_USER" -O "$PG_USER" "$DB_NAME"
fi

echo "[bootstrap] applying migration..."
docker exec -i "$CONTAINER" psql -U "$PG_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 < "$MIGRATION"

echo "[bootstrap] verifying schema..."
docker exec "$CONTAINER" psql -U "$PG_USER" -d "$DB_NAME" -c "\d council_episodic" | head -30

echo "[bootstrap] done. DSN: postgresql://${PG_USER}:<password>@127.0.0.1:5433/${DB_NAME}"
