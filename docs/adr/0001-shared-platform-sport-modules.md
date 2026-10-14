# ADR-0001: Shared platform with sport-specific modules

Status: accepted

## Context

We want to serve six sports. Accounts, permissions, squads, budgets, scheduling and reporting
work the same way in every sport. Statistics, tactical models, video events, roles and
recruitment logic do not. One generic model trained across all six sports would understand
none of them well.

## Decision

- **Core is sport-agnostic.** `packages/core` defines the `SportModule` contract and the logic that works through it, such as like-for-like role comparison. Core code never branches on a sport ID.
- **Each sport is a module.** Each one lives in `packages/sports/<sport>` and provides:
  - roles
  - an event taxonomy
  - metric definitions
  - an exposure unit, such as minutes, possessions, innings or plate appearances
  - default comparison metrics per role

  Later stages will add a video tag schema, valuation inputs and tactical models.
- **Metric definitions are data.** Each module keeps them in a JSON file (for example `packages/sports/soccer/metrics.json`) that the TypeScript app and the Python services both read, so metric keys cannot drift apart.
- **Sport-specific attributes go in `players.attributes` (jsonb).** Shared tables do not get sport-specific columns.
- **Monorepo.** TypeScript for the web app, API and shared packages; Python for data, ML and video services; Postgres for storage; object storage for video.

## Consequences

- Adding a sport means adding a module and its connectors. Accounts, squads and finance are untouched.
- The contract will grow as later stages need more from each sport. Keep it minimal, and extend it only when a second sport needs the same thing.
