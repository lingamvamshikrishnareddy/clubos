# Basketball reference

Generated from `packages/sports/basketball/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Minutes**, values shown per 36; low-sample below 300.

Valuation basis: **annual salary**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Point guard (`point_guard`) | guard | `assists`, `turnovers`, `usage_rate`, `true_shooting_pct`, `three_point_pct`, `steals` |
| Shooting guard (`shooting_guard`) | guard | `points`, `true_shooting_pct`, `three_point_attempts`, `three_point_pct`, `deflections` |
| Small forward (`small_forward`) | forward | `points`, `true_shooting_pct`, `rebounds`, `three_point_pct`, `deflections`, `on_off_net_rating` |
| Power forward (`power_forward`) | forward | `rebounds`, `true_shooting_pct`, `blocks`, `contested_shots`, `screen_assists`, `on_off_net_rating` |
| Centre (`centre`) | big | `rebounds`, `offensive_rebounds`, `blocks`, `contested_shots`, `screen_assists`, `true_shooting_pct` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `points` | Points | per exposure | higher | 6–30 | Points scored. |
| `rebounds` | Rebounds | per exposure | higher | 2–13 | Total rebounds. |
| `offensive_rebounds` | Offensive rebounds | per exposure | higher | 0.3–4 | Rebounds of own team's misses. |
| `assists` | Assists | per exposure | higher | 1–10 | Passes leading directly to a score. |
| `turnovers` | Turnovers | per exposure | lower | 0.8–4 | Possessions lost. |
| `steals` | Steals | per exposure | higher | 0.4–2.2 | Possessions won from the opponent. |
| `blocks` | Blocks | per exposure | higher | 0.1–3 | Opponent shots blocked. |
| `true_shooting_pct` | True shooting % | rate | higher | 0.5–0.66 | Points / (2 × (FGA + 0.44 × FTA)). |
| `three_point_attempts` | 3-point attempts | per exposure | higher | 0.2–10 | Three-point shots attempted. |
| `three_point_pct` | 3-point % | rate | higher | 0.28–0.42 | Three-pointers made / attempted. |
| `free_throw_rate` | Free-throw rate | rate | higher | 0.12–0.45 | Free-throw attempts / field-goal attempts. |
| `usage_rate` | Usage rate | rate | higher | 0.14–0.33 | Share of team possessions used while on court. |
| `on_off_net_rating` | On/off net rating | rate | higher | -6–9 | Team net rating with the player on minus off court, per 100 possessions. |
| `deflections` | Deflections | per exposure | higher | 0.8–4 | Passes or dribbles deflected. |
| `contested_shots` | Contested shots | per exposure | higher | 3–14 | Opponent shots contested. |
| `screen_assists` | Screen assists | per exposure | higher | 0.2–5 | Screens leading directly to a made shot. |

## Event types

`shot`, `free_throw`, `rebound`, `assist`, `turnover`, `steal`, `block`, `foul`, `screen`, `substitution`

## Video tags

- **Play type** (`play_type`): pick and roll ball handler, pick and roll roll man, isolation, post-up, spot-up, handoff, cut, off screen, transition, putback
- **Pick-and-roll coverage** (`pnr_coverage`): drop, switch, hedge, blitz, ice, at the level
- **Team defence** (`defence`): man, 2-3 zone, 3-2 zone, 1-3-1 zone, full-court press
- **Shot zone** (`shot_zone`): rim, short mid-range, long mid-range, corner three, above-the-break three
