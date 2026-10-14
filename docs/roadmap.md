# Roadmap

Stages can overlap when customers need them to. Each stage is a GitHub milestone, created by
the *Bootstrap labels and milestones* workflow.

| Stage | Modules | Why this order |
|---|---|---|
| 1 – Recruitment core | Player database, data imports, comparisons, scouting reports, shortlists, lightweight squad view | A useful recruitment workflow without advanced computer vision |
| 2 – Video and match evidence | Video tagging, clips, event-linked statistics, tactical reports | Adds evidence to recruitment and match decisions |
| 3 – Connected decisions | Tactical-fit recommendations, performance forecasts, budget scenarios | Differentiation through connected decisions |
| 4 – Development and availability | Training loads, development, workload alerts, risk indicators | Needs consistent longitudinal data and careful validation |
| 5 – Squad operations | Attendance, contracts, staff workflows, academy administration | Expands daily usage across the club |
| 6 – Commercial operations | Stadium income, sponsorships, advertising inventory, deals, executive planning | Expands into the club's business |
| 7 – Additional sports | Further sport modules | Reuses the shared foundation |

## Stage 1 status

| Item | Status |
|---|---|
| Sport-module contract (`packages/core`) | Done |
| Like-for-like role comparison with low-sample handling | Done |
| Soccer module: roles, events, metrics | Done |
| Postgres schema: provenance, identity, recruitment | Done |
| StatsBomb open-data aggregation | Done |
| CI: TypeScript, Python, schema | Done |
| Load ingested stats into Postgres, with identity matching | To do |
| API: auth, organisations, roles | To do |
| Web: player search, comparison, scouting reports, shortlists, squad view | To do |
| CSV import with validation | To do |
