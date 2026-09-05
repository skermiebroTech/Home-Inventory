#!/bin/sh
# HomeStock restore, without the API.
#
# It reads a ZIP from backup.sh or from GET /api/export/full, checks the
# schema version, puts the uploads back, and loads the database dump.
#
#   ./restore.sh [-y] [-u] [-d] archive.zip
#
#     -y  do not ask, just restore
#     -u  the uploads only
#     -d  the database only
#
# STOP THE APPLICATION FIRST. A restore replaces every row.

set -eu

UPLOAD_DIR="${HS_UPLOAD_DIR:-${UPLOAD_DIR:-/mnt/user/appdata/home-inventory/uploads}}"
DATABASE_URL="${HS_DATABASE_URL:-${DATABASE_URL:-}}"
SCHEMA_VERSION=1
ASSUME_YES=0
DO_UPLOADS=1
DO_DATABASE=1

usage() {
  sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while getopts "yudh" option; do
  case "$option" in
    y) ASSUME_YES=1 ;;
    u) DO_DATABASE=0 ;;
    d) DO_UPLOADS=0 ;;
    h) usage 0 ;;
    *) usage 1 ;;
  esac
done
shift $((OPTIND - 1))

ARCHIVE="${1:-}"
say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

[ -n "$ARCHIVE" ] || usage 1
[ -f "$ARCHIVE" ] || die "$ARCHIVE does not exist."
command -v unzip >/dev/null 2>&1 || die "unzip is not installed."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

say "Reading $ARCHIVE"
unzip -q "$ARCHIVE" -d "$WORK" || die "The archive is not readable."

[ -f "$WORK/metadata.json" ] || die "This ZIP holds no metadata.json, so it is not a HomeStock backup."

FOUND_VERSION="$(sed -n 's/.*"schema_version"[^"]*"\([^"]*\)".*/\1/p' "$WORK/metadata.json")"
[ -n "$FOUND_VERSION" ] || die "metadata.json names no schema version."
if [ "$FOUND_VERSION" != "$SCHEMA_VERSION" ]; then
  die "The archive uses schema version $FOUND_VERSION. This script reads version $SCHEMA_VERSION."
fi
say "Schema version $FOUND_VERSION. Written $(sed -n 's/.*"generated_at"[^"]*"\([^"]*\)".*/\1/p' "$WORK/metadata.json")."

if [ "$ASSUME_YES" -ne 1 ]; then
  printf 'This replaces the current data. Type yes to go on: '
  read -r answer
  [ "$answer" = "yes" ] || die "Nothing changed."
fi

if [ "$DO_UPLOADS" -eq 1 ] && [ -d "$WORK/uploads" ]; then
  say "Putting the files back into $UPLOAD_DIR"
  mkdir -p "$UPLOAD_DIR"
  cp -R "$WORK/uploads/." "$UPLOAD_DIR/"
  say "Restored $(find "$WORK/uploads" -type f | wc -l | tr -d ' ') files."
fi

if [ "$DO_DATABASE" -eq 1 ]; then
  if [ ! -f "$WORK/database.sql" ]; then
    say "warning: the archive holds no database.sql, so no row changed."
  elif [ -z "$DATABASE_URL" ]; then
    say "warning: no HS_DATABASE_URL, so no row changed."
  elif ! command -v psql >/dev/null 2>&1; then
    say "warning: psql is not installed. Load it by hand:"
    say "  psql --dbname=\"\$HS_DATABASE_URL\" --file=database.sql"
  else
    LIBPQ_URL="$(printf '%s' "$DATABASE_URL" | sed 's/+asyncpg//')"
    say "Loading the database"
    # ON_ERROR_STOP makes psql fail loudly. Without it, it prints the errors
    # and still reports success.
    # The output of the dump goes nowhere, so only the messages of this
    # script reach the operator. An error still shows, on stderr.
    psql --quiet --set ON_ERROR_STOP=1 --output=/dev/null --dbname="$LIBPQ_URL" \
      --file="$WORK/database.sql" || die "psql refused the dump."
    say "The rows are back."
  fi
fi

say "Done. Start the application again."
