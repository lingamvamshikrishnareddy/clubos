# Models

All models live in `services/ml` and run with `clubos-ml run`. Each run writes a
`model_runs` row with a model card (intended use, method, limits) and validation metrics.
Every output links to the run that produced it. These are **explainable baselines**, chosen
so staff can see why a number is what it is. Accuracy can improve later, without losing that.

| Model | Output table | Method | Shown to staff as |
|---|---|---|---|
| `valuation_baseline` | `player_valuations` | Ridge regression on log(value): age, age², role performance score, playing-time share, role group. One model per competition; the target is the transfer fee or the annual salary, depending on the sport. | A range (80% interval) with its three main drivers |
| `forecast_shrinkage` | `performance_forecasts` | Player rate shrunk toward the role average in proportion to playing time, with a small age adjustment | Next-season expectation with a range and how much rests on the player's own data |
| `tactical_fit` | `recommendations` | Weighted role percentiles using the club's style profile | Fit score, the metrics behind it, linked video clips, valuation |
| `workload_indicators` | `workload_indicators` | Acute:chronic workload ratio (7 days vs 28-day weekly average), monotony, recent wellness | Indicators with their inputs, for qualified staff |
| `performance_score` | `player_performance_scores` | Mean direction-aware percentile of the role's comparison metrics | 0–100 role score, used in ROI views and reports |
| `unit_combinations` | `unit_stats` | Shifts split into time slices; time together and value for/against per unit (from `units` in sport.json) | Basketball lineups, hockey forward lines and defence pairs |
| `formation_detection` | `formation_detections` | Average on-ball positions split into lines; closest formation in the sport's vocabulary (from `formation` in sport.json) | In-possession shape with confidence and player positions (not the starting or defensive formation) |
| `financial_forecast` | `financial_forecasts`, `financial_plans`, `financial_plan_lines` | Contracted categories from contracts and deals pro rata; others from year-to-date run rate; three-year plan = commitments + stated assumptions | Full-year projection vs budget with a range; three-year plan with the committed share |
| `player_report` | `player_reports` | Template text over stored data and model outputs; every item names its source table | One-page player summary |

## Validation

Valuation models are cross-validated (5 folds) when trained. The run stores the mean
absolute error in log space and how often the actual value fell inside the stated 80% range
(`cv_interval_coverage_80`). On the demo data, coverage is 73–82% across sports. Ranges
are shown, not just point values, because single numbers overstate certainty.

## Health and availability

Workload indicators are monitoring aids for qualified performance and medical staff. They do
not diagnose injuries, and they do not predict that a player will or will not be injured. The
UI must use the word "indicator" and always show the inputs. Clinical details stay in
`medical_records`, separate from availability status.

## Sport analytics views

These are queries over `match_events`, not models: `v_passing_network` and `v_average_positions` (soccer),
`v_shot_chart` (soccer, basketball, ice hockey), `v_cricket_deliveries` (wagon wheel and pitch map) and
`v_cricket_matchups` (batter vs bowler), `v_pitch_mix` (baseball), `v_play_efficiency` (American football).

## Known limitations

- **No league-strength adjustment.** Percentiles are computed within each player's own league and season.
- **Feature timing.** Valuation features come from the latest season, which may postdate older transactions.
- **Formations are in-possession shapes.** On the World Cup 2022 data, 3-4-3 is the most common detected shape because full-backs push on; out-of-possession shape needs tracking data.
- **Financial run rates ignore seasonality.** For example, match-day income is extrapolated evenly.
- **No automatic video tagging.** Events come from data providers or analysts; computer-vision tagging would need licensed footage and labelled training data.
- **Valuation coverage.** Only competitions with at least 30 market transactions get valuations. For example, World Cup players are compared and recommended but not valued.
