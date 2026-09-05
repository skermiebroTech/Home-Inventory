#!/bin/sh
# Container entrypoint.
#
# 1. Match the file owner to the PUID and PGID that Unraid gives.
# 2. Wait for PostgreSQL.
# 3. Run the database migrations.
# 4. Start uvicorn.
set -e

PUID="${PUID:-99}"
PGID="${PGID:-100}"
APP_PORT="${HS_PORT:-${PORT:-7850}}"
DATA_DIR="${HS_DATA_DIR:-${DATA_DIR:-/data}}"

log() { echo "[entrypoint] $*"; }

# --- File ownership ---
# Unraid runs shares as the user nobody (99) and the group users (100). The
# container writes uploads and backups to a mapped share, so its user must
# hold the same ids.
if [ "$(id -u)" = "0" ]; then
    if ! getent group "$PGID" >/dev/null 2>&1; then
        groupadd -g "$PGID" homestock
    fi
    if ! getent passwd "$PUID" >/dev/null 2>&1; then
        useradd -u "$PUID" -g "$PGID" -M -s /usr/sbin/nologin homestock
    fi
    mkdir -p "$DATA_DIR"
    log "Setting owner of $DATA_DIR to $PUID:$PGID"
    chown -R "$PUID:$PGID" "$DATA_DIR" 2>/dev/null || \
        log "Could not change the owner of every file. Continuing."
fi

# --- Wait for the database ---
# The application container usually starts before PostgreSQL accepts
# connections. Alembic fails at once if it cannot connect, so wait first.
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
if command -v pg_isready >/dev/null 2>&1; then
    i=0
    while [ "$i" -lt 60 ]; do
        if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
            log "PostgreSQL is ready."
            break
        fi
        i=$((i + 1))
        [ "$i" = "1" ] && log "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
        sleep 1
    done
    [ "$i" = "60" ] && log "PostgreSQL did not answer in 60 s. Continuing anyway."
fi

# --- Migrations ---
log "Running database migrations."
cd /app/backend
if alembic upgrade head; then
    log "Migrations are up to date."
else
    # The service still starts. GET /api/health then reports the database as
    # unmigrated, so the operator can read this log and fix it.
    log "ERROR: the migration failed. The API starts, but it will not work."
fi

# The application already migrated here. Do not repeat it on startup.
export HS_RUN_MIGRATIONS_ON_START=false

# --- Start the server ---
log "Starting uvicorn on port $APP_PORT."
cd /app/backend
if [ "$(id -u)" = "0" ] && command -v gosu >/dev/null 2>&1; then
    exec gosu "$PUID:$PGID" uvicorn app.main:app \
        --host 0.0.0.0 --port "$APP_PORT" \
        --log-level "${HS_LOG_LEVEL:-${LOG_LEVEL:-info}}" \
        --proxy-headers --forwarded-allow-ips='*'
fi
exec uvicorn app.main:app \
    --host 0.0.0.0 --port "$APP_PORT" \
    --log-level "${HS_LOG_LEVEL:-${LOG_LEVEL:-info}}" \
    --proxy-headers --forwarded-allow-ips='*'
