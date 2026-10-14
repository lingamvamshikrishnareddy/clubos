#!/usr/bin/env bash
# Builds a demo database: schema, fictional data for all six sports, optionally the real
# StatsBomb FIFA World Cup 2022 data, then every model output.
#
#   DATABASE_URL=postgresql://localhost/clubos_demo scripts/demo-db.sh [--with-statsbomb]
#
# The database must exist and be empty.
set -euo pipefail

: "${DATABASE_URL:?Set DATABASE_URL to an empty database}"
root="$(cd "$(dirname "$0")/.." && pwd)"
as_of="${AS_OF:-$(date +%F)}"

echo "Applying migrations"
for f in "$root"/db/migrations/*.sql; do
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done

echo "Loading fictional demo data (as of $as_of)"
(cd "$root/services/ingest" && uv run --quiet clubos-mock-data --as-of "$as_of")

if [[ "${1:-}" == "--with-statsbomb" ]]; then
  echo "Loading StatsBomb open data: FIFA World Cup 2022"
  (cd "$root/services/ingest" && uv run --quiet clubos-ingest-statsbomb load 43 106)
fi

echo "Running models"
(cd "$root/services/ml" && uv run --quiet clubos-ml run --as-of "$as_of")
