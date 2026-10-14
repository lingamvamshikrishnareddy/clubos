# Services (Python)

- `ingest/` – data connectors. Starts with StatsBomb open data for soccer.
- `ml/` – valuation, forecasts, similarity and tactical-fit models (Stage 3+). Every model ships with a model card.
- `video/` – video ingest, clipping and event-to-timestamp linking (Stage 2). Video lives in object storage, never in git.
