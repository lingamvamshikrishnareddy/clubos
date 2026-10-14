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

## Known limitations

- **No league-strength adjustment.** Percentiles are computed within each player's own league and season.
- **Feature timing.** Valuation features come from the latest season, which may postdate older transactions.
- **Valuation coverage.** Only competitions with at least 30 market transactions get valuations. For example, World Cup players are compared and recommended but not valued.
