# ClubOS

An AI-assisted sports intelligence and club operating system: one platform that helps a club
discover talent, recruit the right players, improve performance and availability, analyse
matches, manage its squad, and run the business behind the team.

The product is built as **a shared platform with sport-specific intelligence modules**.
Accounts, data, squads, budgets, permissions and reporting are shared. Statistics, tactical
models, video events and recruitment methods stay specific to each sport. The first sport is
**association football (soccer)**.

The differentiator is the connection between three layers in one workflow:

| Layer | Helps the club… |
|---|---|
| Sports intelligence | make better sporting decisions (recruitment, ML, match analysis, development) |
| Club operating system | run the squad and coordinate daily work |
| Business & commercial | control costs and generate revenue |

Every feature should answer one of four questions: *Who should we sign? Where are we losing
performance? How do we improve availability and development? How do we allocate our budget?*

Read more: [vision](docs/vision.md) · [roadmap](docs/roadmap.md) ·
[architecture decisions](docs/adr) · [soccer spec](docs/sports/soccer.md)

## Repository layout

```
apps/              web app and API (Stage 1, in progress)
packages/core      sport-agnostic domain types and comparison logic
packages/sports/*  one module per sport (soccer first)
services/ingest    Python data connectors (StatsBomb open data)
db/migrations      Postgres schema
docs/              vision, roadmap, ADRs, sport specs
```

## Development

Requirements: Node 22+, pnpm 10, Python 3.12+, [uv](https://docs.astral.sh/uv/), Postgres 16.

```sh
pnpm install
pnpm typecheck && pnpm test

cd services/ingest && uv run --group dev pytest

# Apply the schema to a local database
for f in db/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -f "$f"; done
psql -v ON_ERROR_STOP=1 -f db/tests/smoke.sql

# Ingest one StatsBomb open-data match (prints per-player stats as JSON lines)
cd services/ingest && uv run clubos-ingest-statsbomb 3788741
```

## Data

No third-party data or video is committed to this repository. Connectors fetch data at ingest
time and record its source and licence (see [ADR-0002](docs/adr/0002-data-provenance-and-identity.md)).
Soccer open data: [StatsBomb Open Data](https://github.com/statsbomb/open-data), used under
its licence with attribution.
