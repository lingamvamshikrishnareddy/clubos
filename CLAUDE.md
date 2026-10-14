# ClubOS – notes for Claude

- Read README.md, docs/vision.md and docs/adr/ before changing architecture.
- `packages/core` must stay sport-agnostic: no branching on sport IDs. Sport logic goes in `packages/sports/<sport>`.
- Each sport is defined as data in `packages/sports/<sport>/sport.json` (roles, exposure, events, video tags, metrics), shared by TypeScript and Python. Tests check the Python code uses only keys defined there.
- Missing data stays `null` or absent, never `0`. Imported rows carry provenance (ADR-0002).
- Never commit third-party data, video or secrets.

Checks to run before pushing:

    pnpm typecheck && pnpm test
    (cd services/ingest && uv run --group dev pytest -q)
    for f in db/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -q -f "$f"; done && psql -v ON_ERROR_STOP=1 -q -f db/tests/smoke.sql
