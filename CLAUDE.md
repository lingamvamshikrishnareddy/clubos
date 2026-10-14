# ClubOS – notes for Claude

- Read README.md, docs/vision.md and docs/adr/ before changing architecture.
- `packages/core` must stay sport-agnostic: no branching on sport IDs. Sport logic goes in `packages/sports/<sport>`.
- Each sport is defined as data in `packages/sports/<sport>/sport.json` (roles, exposure, events, video tags, metrics), shared by TypeScript and Python. Tests check the Python code uses only keys defined there.
- Missing data stays `null` or absent, never `0`. Imported rows carry provenance (ADR-0002).
- Never commit third-party data, video or secrets.

- Model outputs come from `services/ml` and always reference a model run; health outputs are "indicators", never diagnoses (ADR-0003).
- Demo data is fictional, deterministic and recorded under the `mock` source. Never present it as real.
- Real leagues live in `packages/leagues/leagues.json`; every rule names its season and must be reviewed each season. Connectors load into these competitions (`clubos-leagues`, `clubos-ingest-nflverse`, `clubos-ingest-cricsheet`).
- Access control lives in Postgres row-level security (ADR-0004). New club-private tables need a policy in a migration and a case in `db/tests/rls.sql`; new views must be created `with (security_invoker = true)`.

Checks to run before pushing (Python database tests need CLUBOS_TEST_DATABASE_URL pointing at a migrated database):

    pnpm typecheck && pnpm test && python3 scripts/sport-docs.py --check
    (cd services/ingest && uv run --group dev pytest -q)
    (cd services/ml && uv run --group dev pytest -q)
    for f in db/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -q -f "$f"; done
    psql -v ON_ERROR_STOP=1 -q -f db/tests/smoke.sql && psql -v ON_ERROR_STOP=1 -q -f db/tests/rls.sql
    DATABASE_URL=<empty db> scripts/demo-db.sh
