# American football reference

Generated from `packages/sports/american-football/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Snaps**, values shown per 60; low-sample below 150.
- `kicker`: **Kicks**, per 1; low-sample below 15.
- `punter`: **Punts**, per 1; low-sample below 15.

Valuation basis: **annual salary**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Quarterback (`quarterback`) | offence | `epa_per_play`, `completion_pct`, `passing_yards`, `passing_tds`, `interceptions_thrown` |
| Running back (`running_back`) | offence | `rushing_yards`, `yards_per_carry`, `receptions`, `yards_after_catch`, `epa_per_play` |
| Wide receiver (`wide_receiver`) | offence | `receiving_yards`, `targets`, `receptions`, `yards_after_catch`, `drops` |
| Tight end (`tight_end`) | offence | `receiving_yards`, `receptions`, `pass_block_win_rate`, `run_block_win_rate`, `drops` |
| Offensive lineman (`offensive_line`) | offence | `pass_block_win_rate`, `run_block_win_rate` |
| Defensive lineman (`defensive_line`) | defence | `pressures`, `sacks`, `tackles`, `missed_tackle_pct` |
| Edge rusher (`edge_rusher`) | defence | `pressures`, `sacks`, `tackles`, `missed_tackle_pct` |
| Linebacker (`linebacker`) | defence | `tackles`, `missed_tackle_pct`, `pressures`, `passes_defended`, `yards_per_coverage_snap` |
| Cornerback (`cornerback`) | defence | `yards_per_coverage_snap`, `passes_defended`, `tackles`, `missed_tackle_pct` |
| Safety (`safety`) | defence | `yards_per_coverage_snap`, `passes_defended`, `tackles`, `missed_tackle_pct` |
| Kicker (`kicker`) | special teams | `field_goal_pct` |
| Punter (`punter`) | special teams | `net_punt_avg` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `passing_yards` | Passing yards | per exposure | higher | 80–320 | Yards gained on completed passes. |
| `pass_attempts` | Pass attempts | per exposure | higher | 15–45 | Forward passes thrown. |
| `completion_pct` | Completion % | rate | higher | 0.55–0.72 | Completed passes / attempts. |
| `passing_tds` | Passing touchdowns | per exposure | higher | 0.5–3 | Touchdown passes thrown. |
| `interceptions_thrown` | Interceptions thrown | per exposure | lower | 0.2–1.5 | Passes intercepted by the defence. |
| `epa_per_play` | EPA per play | rate | higher | -0.15–0.3 | Expected points added per play involved in. |
| `rushing_yards` | Rushing yards | per exposure | higher | 10–120 | Yards gained on rushes. |
| `yards_per_carry` | Yards per carry | rate | higher | 3.2–5.6 | Rushing yards / rushes. |
| `targets` | Targets | per exposure | higher | 2–11 | Passes thrown towards the player. |
| `receptions` | Receptions | per exposure | higher | 1–8 | Passes caught. |
| `receiving_yards` | Receiving yards | per exposure | higher | 15–110 | Yards gained on receptions. |
| `yards_after_catch` | Yards after catch | per exposure | higher | 5–45 | Receiving yards gained after the catch. |
| `drops` | Drops | per exposure | lower | 0–0.8 | Catchable passes dropped. |
| `pass_block_win_rate` | Pass block win rate | rate | higher | 0.82–0.95 | Share of pass-block snaps sustained for 2.5 s. |
| `run_block_win_rate` | Run block win rate | rate | higher | 0.65–0.78 | Share of run-block snaps won. |
| `pressures` | Pressures | per exposure | higher | 0.5–6 | Hurries, hits and sacks on the quarterback. |
| `sacks` | Sacks | per exposure | higher | 0–1.2 | Quarterback sacks (half sacks count 0.5). |
| `tackles` | Tackles | per exposure | higher | 1–10 | Solo and assisted tackles. |
| `missed_tackle_pct` | Missed tackle % | rate | lower | 0.05–0.2 | Missed tackles / tackle attempts. |
| `passes_defended` | Passes defended | per exposure | higher | 0.1–1.5 | Pass break-ups and interceptions. |
| `yards_per_coverage_snap` | Yards allowed per coverage snap | rate | lower | 0.6–1.6 | Receiving yards allowed in coverage / coverage snaps. |
| `field_goal_pct` | Field goal % | rate | higher | 0.75–0.94 | Field goals made / attempted. |
| `net_punt_avg` | Net punting average | rate | higher | 38–45 | Net yards per punt after returns. |

## Event types

`pass`, `rush`, `reception`, `sack`, `pressure`, `tackle`, `interception`, `fumble`, `penalty`, `field_goal`, `punt`, `kickoff`

## Video tags

- **Offensive formation** (`offensive_formation`): shotgun, singleback, I-formation, pistol, empty, under centre
- **Personnel** (`personnel`): 11, 12, 13, 21, 22, 10
- **Coverage** (`coverage`): cover 0, cover 1, cover 2, cover 3, cover 4, cover 6, man, zone
- **Route** (`route`): slant, out, in, go, post, corner, curl, flat, screen, wheel
- **Pressure** (`pressure`): blitz, simulated pressure, four-man rush, stunt
- **Down and distance** (`down_distance`): 1st & 10, 2nd & long, 2nd & short, 3rd & long, 3rd & short, 4th down, red zone, two-minute
