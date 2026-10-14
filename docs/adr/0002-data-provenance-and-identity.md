# ADR-0002: Data provenance, context, identity and missing data

Status: accepted

## Context

Recommendations are only as good as the data under them. Without provenance, competition
context and consistent identities, models can be confidently wrong. Data licences also limit
what we may store and show.

## Decision

1. **Provenance on every imported fact.**
   - Each appearance row carries `source_id`, `source_record_id`, `ingestion_run_id` and `ingested_at`.
   - `data_sources` records the licence and attribution for each source.
2. **Competition context.**
   - Matches belong to a season of a competition.
   - Competitions record gender, youth status and a strength `tier`. This lets comparisons across leagues be adjusted rather than treated as equal.
3. **One player, many provider IDs.**
   - `player_identities` maps `(source_id, external_id)` to an internal `player_id`, with `match_method` and `confidence`.
   - A probabilistic match counts as unverified until a person confirms it (`verified_by`).
4. **Missing is not zero.**
   - A missing metric row means the source did not provide that metric. A `null` value means the source provided the field without a value. Code never coerces either to `0`.
   - Players below the sport's minimum exposure are flagged as low-sample and left out of the comparison pool.
5. **No third-party data or video in git.**
   - Connectors fetch data at ingest time.
   - Video goes to object storage.
   - New providers go through the *Data source request* issue template, which asks about licence terms before any code is written.

## Consequences

- Every number on screen can be traced back to its source, which makes it explainable to staff.
- Identity matching needs a review queue in the UI. That work is planned in Stage 1.
