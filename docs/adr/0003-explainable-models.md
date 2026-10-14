# ADR-0003: Explainable baseline models, run as batch jobs

Status: accepted

## Context

Clubs act on recommendations that involve money, careers and health. Staff need to know why a
player is recommended and how certain the numbers are. We also have little labelled data
early on, and it differs widely between sports.

## Decision

- **Batch jobs in Python.** Models live in `services/ml` and run as batch jobs that write their outputs to Postgres. The web app reads stored outputs and never trains models.
- **Every run is recorded.** Each run writes a `model_runs` row with a model card (intended use, method, training data, limitations) and validation metrics. Every output references its run.
- **Explainable first.** Start with models whose reasoning can be shown: ridge regression with feature contributions, shrinkage estimates, weighted percentiles. Replace a model only when a better one beats it on stored validation metrics and can still explain its outputs.
- **Ranges, not points.** Valuations and forecasts are stored and shown with intervals.
- **Sport differences come from `sport.json`.** Roles, metrics, exposure units and valuation basis are read from each sport's definition; model code does not branch on sport.
- **Health outputs are indicators.** They are decision support for qualified staff and never diagnoses (see [models](../models.md)).

## Consequences

- Percentile logic exists in both TypeScript (`packages/core`, for interactive comparison) and Python (`services/ml`). Both follow the same rule (direction-aware, mid-rank for ties) and are tested on the same examples; Python keeps one decimal place where TypeScript rounds to a whole number.
- Valuations are only produced where enough market data exists; elsewhere the UI says "not valued" instead of guessing.
