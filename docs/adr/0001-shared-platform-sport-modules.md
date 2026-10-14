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
  - an exposure unit, such as minutes, snaps or plate appearances, with per-role overrides where a sport measures roles differently (pitchers by batters faced, bowlers by balls bowled)
  - default comparison metrics per role
  - a video tag vocabulary (formations, coverages, pitch types, lengths...)
- **Sport definitions are data.** Each module is a `sport.json` file (for example `packages/sports/soccer/sport.json`) holding roles, exposure units, events, video tags and metrics. The TypeScript app (via `defineSport`, which validates it) and the Python services both read it, so keys cannot drift apart.
- **Sport-specific attributes go in `players.attributes` (jsonb).** Shared tables do not get sport-specific columns.
- **Monorepo.** TypeScript for the web app, API and shared packages; Python for data, ML and video services; Postgres for storage; object storage for video.

## Consequences

- Adding a sport means adding a module and its connectors. Accounts, squads and finance are untouched.
- The contract will grow as later stages need more from each sport. Keep it minimal, and extend it only when a second sport needs the same thing.
