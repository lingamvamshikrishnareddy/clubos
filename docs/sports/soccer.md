# Soccer module

Code: `packages/sports/soccer`. Definition (roles, metrics, video tags): `packages/sports/soccer/sport.json`
(shared with `services/ingest`).

## Exposure

Minutes played. Per-exposure metrics are shown per 90 minutes. Players with fewer than
450 minutes are flagged as low-sample and left out of the comparison pool.

## Roles

Comparisons use roles rather than nominal positions:

- goalkeeper
- centre-back
- full-back / wing-back
- defensive midfielder
- central midfielder
- attacking midfielder
- winger
- striker

Assigning a provider's position to one of these roles is the ingestion layer's job.

## Metrics (Stage 1)

These are computed from StatsBomb open-data events:

- **Shooting:** goals, non-penalty xG, shots
- **Chance creation:** expected assists, key passes
- **Passing:** passes attempted and completed, progressive passes
- **Ball carrying:** progressive carries, successful dribbles
- **Defending:** pressures, tackles won, interceptions, ball recoveries

**Progressive pass or carry:** the action starts outside the defensive 40% of the pitch and
ends at least 25% closer to the centre of the opponent's goal. For passes, only completed
passes count.

## Ingestion rules

- **Penalty shoot-outs (period 5)** are excluded from all metrics and from minutes played.
- **Unused substitutes** get no appearance, even if they appear in the events (for example, booked on the bench).
- **Roles** come from the position the player held most often in the match. Unknown positions stay unknown.

## Known gaps

- **Minutes:** sending-offs and injuries without a substitution are not yet handled. The player is credited until full time.
- **Goalkeepers:** no shot-stopping metric yet (needs post-shot xG). Goalkeeper comparison covers distribution only.
- **League strength:** no adjustment yet. Competitions have a `tier` column ready for it.

## Later stages

- Passing networks
- Pressing intensity (PPDA)
- Formation detection from tracking data
- Tactical fit against a club's style profile
- Transfer valuation
