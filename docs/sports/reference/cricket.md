# Cricket reference

Generated from `packages/sports/cricket/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Balls faced**, values shown per 100; low-sample below 150.
- `fast_bowler`: **Balls bowled**, per 120; low-sample below 360.
- `spin_bowler`: **Balls bowled**, per 120; low-sample below 360.
- `bowler`: **Balls bowled**, per 120; low-sample below 360.

Valuation basis: **annual salary**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Opening batter (`opening_batter`) | batting | `runs`, `batting_strike_rate`, `batting_average`, `boundary_pct`, `control_pct` |
| Top-order batter (`top_order_batter`) | batting | `runs`, `batting_average`, `batting_strike_rate`, `control_pct`, `batting_dot_pct` |
| Middle-order batter (`middle_order_batter`) | batting | `runs`, `batting_average`, `batting_strike_rate`, `batting_dot_pct`, `sixes` |
| Finisher (`finisher`) | batting | `batting_strike_rate`, `sixes`, `boundary_pct`, `batting_dot_pct`, `runs` |
| Wicketkeeper-batter (`wicketkeeper_batter`) | batting | `keeper_dismissals`, `runs`, `batting_strike_rate`, `batting_average` |
| All-rounder (`all_rounder`) | all-round | `runs`, `batting_strike_rate`, `wickets`, `economy_rate`, `catches` |
| Fast bowler (`fast_bowler`) | bowling | `wickets`, `economy_rate`, `bowling_strike_rate`, `bowling_dot_pct`, `average_speed` |
| Spin bowler (`spin_bowler`) | bowling | `wickets`, `economy_rate`, `bowling_average`, `bowling_dot_pct`, `bowling_strike_rate` |
| Bowler (style not recorded) (`bowler`) | bowling | `wickets`, `economy_rate`, `bowling_strike_rate`, `bowling_average`, `bowling_dot_pct` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `runs` | Runs | per exposure | higher | 80–170 | Runs scored off the bat. |
| `batting_strike_rate` | Batting strike rate | rate | higher | 70–170 | Runs per 100 balls faced. |
| `batting_average` | Batting average | rate | higher | 15–55 | Runs per dismissal. |
| `boundary_pct` | Boundary % | rate | higher | 0.06–0.25 | Balls faced hit for four or six. |
| `batting_dot_pct` | Dot-ball % (batting) | rate | lower | 0.25–0.5 | Balls faced without scoring. |
| `sixes` | Sixes | per exposure | higher | 0.5–9 | Sixes hit. |
| `control_pct` | Control % | rate | higher | 0.72–0.9 | Balls faced with a controlled shot or leave. |
| `wickets` | Wickets | per exposure | higher | 2.5–7.5 | Wickets taken. |
| `economy_rate` | Economy rate | rate | lower | 4–9.5 | Runs conceded per over. |
| `bowling_average` | Bowling average | rate | lower | 18–40 | Runs conceded per wicket. |
| `bowling_strike_rate` | Bowling strike rate | rate | lower | 14–45 | Balls bowled per wicket. |
| `bowling_dot_pct` | Dot-ball % (bowling) | rate | higher | 0.3–0.55 | Deliveries not scored from. |
| `average_speed` | Average speed | rate | higher | 80–145 | Mean release speed. |
| `catches` | Catches | per exposure | higher | 0.2–3 | Catches taken. |
| `keeper_dismissals` | Keeper dismissals | per exposure | higher | 1–5 | Catches and stumpings as wicketkeeper. |

## Event types

`delivery`, `run`, `boundary_four`, `boundary_six`, `wicket`, `extra`, `catch`, `run_out`, `stumping`, `review`

## Video tags

- **Length** (`length`): yorker, full, good length, back of a length, short
- **Line** (`line`): wide outside off, outside off, stumps, leg stump, down leg
- **Delivery type** (`delivery_type`): outswinger, inswinger, seam up, cutter, slower ball, bouncer, off-break, leg-break, googly, arm ball, carrom ball
- **Shot** (`shot`): drive, cut, pull, hook, sweep, reverse sweep, flick, defence, leave, scoop
- **Phase** (`phase`): powerplay, middle overs, death overs, new ball, old ball
- **Field setting** (`field`): attacking, ring field, boundary riders, leg-side trap, off-side heavy
