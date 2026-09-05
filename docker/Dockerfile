# HomeStock production image.
#
# Stage 1 builds the React web interface.
# Stage 2 holds the Python API and serves the built interface as static files.
#
# Build from the repository root:
#   docker build -f docker/Dockerfile -t homestock:latest .

# ---------------------------------------------------------------------------
# Stage 1: the web interface
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend

WORKDIR /build

# The lock file is copied first, so a source change does not repeat the
# install step.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: the API
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HS_STATIC_DIR=/app/static \
    HS_DATA_DIR=/data \
    HS_UPLOAD_DIR=/data/uploads \
    HS_BACKUP_DIR=/data/backups \
    HS_CONFIG_DIR=/data/config

# System packages:
#   tesseract-ocr        reads the text on a receipt. It runs on the CPU.
#   postgresql-client-16 supplies pg_dump for the backup feature. The version
#                        must match the server, because an older pg_dump
#                        refuses to dump a newer server. Debian ships another
#                        version, so the PGDG repository is added below. The
#                        codename comes from /etc/os-release, because the base
#                        image moves from one Debian release to the next.
#   gosu                 drops from root to the PUID and PGID that Unraid gives.
#   curl                 runs the container healthcheck.
#   zip, unzip           the standalone scripts in /app/scripts read and write
#                        the archive, so they run inside the container too.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg gosu zip unzip \
        tesseract-ocr tesseract-ocr-eng \
        libjpeg62-turbo zlib1g libfreetype6; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc; \
    . /etc/os-release; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-16; \
    apt-get purge -y --auto-remove gnupg; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY --from=frontend /build/dist ./static

RUN chmod +x /app/backend/entrypoint.sh

EXPOSE 7850
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:7850/api/health || exit 1

ENTRYPOINT ["/app/backend/entrypoint.sh"]
