#!/bin/sh
# HomeStock backup, without the API.
#
# Run this on the Unraid server, from cron or by hand. It writes one ZIP that
# holds the database dump, every uploaded file, and a metadata file. The
# archive has the same shape as the one from GET /api/export/full, so
# restore.sh and the API both read it.
#
#   ./backup.sh [-o output-dir] [-k keep] [-r rclone-remote]
#
# It reads the same environment variables as the container. Point it at a
# .env file with:  set -a; . ./.env; set +a; ./scripts/backup.sh

set -eu

OUTPUT_DIR="${HS_BACKUP_DIR:-${BACKUP_DIR:-/mnt/user/appdata/home-inventory/backups}}"
UPLOAD_DIR="${HS_UPLOAD_DIR:-${UPLOAD_DIR:-/mnt/user/appdata/home-inventory/uploads}}"
DATABASE_URL="${HS_DATABASE_URL:-${DATABASE_URL:-}}"
KEEP="${HS_BACKUP_RETENTION:-${BACKUP_RETENTION:-7}}"
RCLONE_REMOTE="${HS_RCLONE_REMOTE:-${RCLONE_REMOTE:-}}"
SCHEMA_VERSION=1

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while getopts "o:k:r:h" option; do
  case "$option" in
    o) OUTPUT_DIR="$OPTARG" ;;
    k) KEEP="$OPTARG" ;;
    r) RCLONE_REMOTE="$OPTARG" ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v zip >/dev/null 2>&1 || die "zip is not installed."

STAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="$OUTPUT_DIR/homestock-backup-$STAMP.zip"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

mkdir -p "$OUTPUT_DIR"
say "Writing $ARCHIVE"

# --- The database ---
if [ -n "$DATABASE_URL" ]; then
  if command -v pg_dump >/dev/null 2>&1; then
    # pg_dump reads a libpq URL. The application uses the asyncpg driver name,
    # which libpq does not know, so it goes away here.
    LIBPQ_URL="$(printf '%s' "$DATABASE_URL" | sed 's/+asyncpg//')"
    say "Reading the database"
    pg_dump --no-owner --no-privileges --format=plain --dbname="$LIBPQ_URL" \
      > "$WORK/database.sql" || die "pg_dump failed."
  else
    say "warning: pg_dump is missing, so the archive holds the files only."
  fi
else
  say "warning: no HS_DATABASE_URL, so the archive holds the files only."
fi

# --- The uploads ---
UPLOAD_COUNT=0
if [ -d "$UPLOAD_DIR" ]; then
  mkdir -p "$WORK/uploads"
  cp -R "$UPLOAD_DIR/." "$WORK/uploads/" 2>/dev/null || true
  UPLOAD_COUNT="$(find "$WORK/uploads" -type f | wc -l | tr -d ' ')"
  say "Copied $UPLOAD_COUNT files"
else
  say "warning: $UPLOAD_DIR does not exist."
fi

# --- The metadata ---
cat > "$WORK/metadata.json" <<JSON
{
  "schema_version": "$SCHEMA_VERSION",
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "application": "HomeStock",
  "written_by": "scripts/backup.sh",
  "upload_file_count": $UPLOAD_COUNT
}
JSON

(cd "$WORK" && zip -q -r "$ARCHIVE" .) || die "The archive could not be written."
say "Wrote $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# --- The retention rule ---
if [ "$KEEP" -gt 0 ] 2>/dev/null; then
  COUNT="$(ls -1t "$OUTPUT_DIR"/homestock-backup-*.zip 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$COUNT" -gt "$KEEP" ]; then
    ls -1t "$OUTPUT_DIR"/homestock-backup-*.zip | tail -n +"$((KEEP + 1))" |
      while read -r old; do
        say "Removing $old"
        rm -f "$old"
      done
  fi
fi

# --- The copy to another place ---
if [ -n "$RCLONE_REMOTE" ]; then
  if command -v rclone >/dev/null 2>&1; then
    say "Copying to $RCLONE_REMOTE"
    rclone copy --no-traverse "$ARCHIVE" "$RCLONE_REMOTE" || say "warning: rclone failed."
  else
    say "warning: rclone is not installed, so the archive stayed here."
  fi
fi

say "Done."
