# ClubOS

An AI-assisted sports intelligence and club operating system: one platform that helps a club
discover talent, recruit the right players, improve performance and availability, analyse
matches, manage its squad, and run the business behind the team.

The product is **a shared platform with sport-specific intelligence modules**. Accounts, data,
squads, budgets, permissions and reporting are shared. Statistics, roles, tactical vocabulary,
video tags and valuation logic are defined per sport. Six sports are supported:

| Sport | Module | Measured in | Valued by |
|---|---|---|---|
| Association football (soccer) | `packages/sports/soccer` | minutes (per 90) | transfer fee |
| American football | `packages/sports/american-football` | snaps (per 60); kicks, punts | annual salary |
| Baseball | `packages/sports/baseball` | plate appearances; batters faced for pitchers | annual salary |
| Basketball | `packages/sports/basketball` | minutes (per 36) | annual salary |
| Ice hockey | `packages/sports/ice-hockey` | time on ice (per 60); shots against for goaltenders | annual salary |
| Cricket | `packages/sports/cricket` | balls faced (per 100); balls bowled for bowlers | annual salary |

Every feature answers one of four questions: *Who should we sign? Where are we losing
performance? How do we improve availability and development? How do we allocate our budget?*

Read more: [vision](docs/vision.md) · [roadmap](docs/roadmap.md) · [architecture decisions](docs/adr) ·
[models](docs/models.md) · [demo data](docs/demo-data.md) · [sport reference](docs/sports/reference)

## Repository layout

```
packages/core      sport-agnostic logic: sport contract, role comparison, squad depth, budget scenarios
packages/sports/*  one module per sport, defined as data in sport.json
services/ingest    data connectors (StatsBomb open data) and the fictional demo-data generator
services/ml        valuation, forecasts, tactical fit and workload indicators
db/migrations      Postgres schema for every stage
scripts/           demo database build, sport reference docs
apps/              web app and API (next)
docs/              vision, roadmap, ADRs, models, sport reference
```

## Try it: build a demo database

Requirements: Node 22+, pnpm 10, Python 3.12+, [uv](https://docs.astral.sh/uv/), Postgres 16.

```sh
createdb clubos_demo
DATABASE_URL=postgresql://localhost/clubos_demo scripts/demo-db.sh --with-statsbomb
```

The script runs four steps:
1. It applies the schema.
2. It loads fictional demo data for all six sports: leagues, two seasons, and one club per sport with staff, contracts, scouting, video, training load, academy, finance and commercial data.
3. With `--with-statsbomb`, it adds the real FIFA World Cup 2022 event data.
4. It runs every model.

The whole build takes about 30 seconds. Then try:

```sql
-- Who should we sign? Tactical-fit recommendations with valuation ranges
select p.full_name, r.role_key, r.fit_score, v.value_low, v.value_high, v.currency, r.reasons
from recommendations r join players p on p.id = r.player_id
left join player_valuations v on v.id = r.valuation_id
order by r.fit_score desc limit 10;

-- How do we allocate our budget?
select * from v_budget_vs_actual;
select * from v_wage_bill;
select * from v_squad_value;

-- Availability: workload indicators flagged for staff review
select p.full_name, w.acwr, w.monotony, w.wellness_score, w.flags
from workload_indicators w join players p on p.id = w.player_id where w.flags <> '{}';
```

## Development

```sh
pnpm install
pnpm typecheck && pnpm test
python3 scripts/sport-docs.py --check

# Python services; database tests run when CLUBOS_TEST_DATABASE_URL points at a migrated database
(cd services/ingest && uv run --group dev pytest)
(cd services/ml && uv run --group dev pytest)

# Real data: one StatsBomb match, or a whole competition-season into Postgres
(cd services/ingest && uv run clubos-ingest-statsbomb match 3857276)
(cd services/ingest && DATABASE_URL=... uv run clubos-ingest-statsbomb load 43 106)
```

## Data

- **No real third-party data in git.** No third-party data or video is committed to this repository. Connectors fetch data at ingest time and record its source and licence (see [ADR-0002](docs/adr/0002-data-provenance-and-identity.md)).
- **Soccer open data:** [StatsBomb Open Data](https://github.com/statsbomb/open-data), used under its licence with attribution.
- **Demo data is fictional.** All clubs, leagues, people and results in the demo data are invented, and they are recorded under the `mock` data source.
