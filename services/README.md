# Services (Python)

- `ingest/` – data connectors (StatsBomb open data for soccer) and the fictional demo-data generator (`clubos-mock-data`).
- `ml/` – valuation, performance forecasts, tactical-fit recommendations and workload indicators (`clubos-ml run`). See [docs/models.md](../docs/models.md).
- `video/` – planned: video ingest and automatic tagging (Stage 2). Video lives in object storage, never in git.

Both packages read sport definitions from `packages/sports/*/sport.json` (override with `CLUBOS_SPORTS_DIR`).
