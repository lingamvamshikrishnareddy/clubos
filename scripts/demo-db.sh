#!/usr/bin/env bash
# Builds a demo database: schema, real league structures and rules, fictional data for all
# six sports, optional real data, then every model output.
#
#   DATABASE_URL=postgresql://localhost/clubos_demo scripts/demo-db.sh [options]
#
#   --with-statsbomb      FIFA World Cup 2022 (StatsBomb open data)
#   --with-nfl SEASON     NFL season from nflverse, e.g. 2024
#   --with-ipl SOURCE     IPL from Cricsheet: ipl_json.zip, a directory of match files, or
#                         https://cricsheet.org/downloads/ipl_json.zip
#
# The database must exist and be empty.
set -euo pipefail

: "${DATABASE_URL:?Set DATABASE_URL to an empty database}"
root="$(cd "$(dirname "$0")/.." && pwd)"
as_of="${AS_OF:-$(date +%F)}"
ingest() { (cd "$root/services/ingest" && uv run --quiet "$@"); }

echo "Applying migrations"
for f in "$root"/db/migrations/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done

echo "Loading league structures and rules"
ingest clubos-leagues load

echo "Loading fictional demo data (as of $as_of)"
ingest clubos-mock-data --as-of "$as_of"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-statsbomb)
      echo "Loading StatsBomb open data: FIFA World Cup 2022"
      ingest clubos-ingest-statsbomb load 43 106
      shift ;;
    --with-nfl)
      echo "Loading NFL $2 from nflverse"
      ingest clubos-ingest-nflverse load "$2"
      shift 2 ;;
    --with-ipl)
      echo "Loading IPL from Cricsheet ($2)"
      ingest clubos-ingest-cricsheet load "$2"
      shift 2 ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2 ;;
  esac
done

echo "Running models"
(cd "$root/services/ml" && uv run --quiet clubos-ml run --as-of "$as_of")
