# Product vision

## Three connected layers

### 1. Sports intelligence: better sporting decisions

- **Recruitment and scouting:** player valuation, talent discovery, squad fit, transfer recommendations.
- **Predictive ML:** performance forecasts with uncertainty, and workload and risk indicators.
- **Match intelligence:** video tagging, clips, formations, tactics, passing networks, opponent weaknesses.
- **Player development:** training loads, fitness trends, progress against goals, performance reports.

### 2. Club operating system: running the squad day to day

- **Squad and availability:** roster, contracts, attendance, player status.
- **Training and staff:** schedules, tasks, communication, goals.
- **Performance workflows:** assessments, reports, medical permissions.
- **Facilities:** bookings, stadium usage, registrations.

### 3. Business and commercial operations: costs and revenue

- **Finance and budgets:** payroll, transfer budgets, expenses, forecasts.
- **Commercial revenue:** sponsorships, advertising inventory, stadium deals.
- **Academy and payments:** registration, fees, collections, renewals.
- **Executive reporting:** revenue, cost per player, squad value, performance ROI.

## The differentiator

The layers are connected. A sporting director can see, in one workflow:

- a recommended player and the tactical reason to sign them
- the video evidence
- the expected salary and transfer cost
- the effect on squad balance
- the budget that would remain

## Decisions, not dashboards

Every module must help answer at least one of these questions:

1. **Who should we sign?** Candidates compared like for like in equivalent roles, plus cost, tactical fit, undervalued talent, and the evidence behind each recommendation.
2. **Where are we losing performance?** Recurring tactical weaknesses, ineffective shapes, poor decision patterns, opponent-specific problems, and declining individual output.
3. **How do we improve availability and development?** Workload, fitness trends, progress against goals, and risk indicators. These *support* qualified medical and performance staff. They never diagnose injuries or promise that a player will stay injury-free.
4. **How do we allocate our budget?** Recruitment scenarios, wages, contract commitments, staffing, stadium costs, and commercial income.

## Positioning

This is an established market. Hudl (including StatsBomb, Wyscout and Instat), TrackMan,
Rapsodo, Cricket-21 and NV Play cover parts of it. We will not claim to be the first AI sports
analytics product. Our aim is to be the **more integrated, affordable and explainable
decision platform** for a specific customer segment, and then expand from there.

## Six sports, six intelligence engines

The shared foundation serves every sport. Each sport gets its own module: event model, roles,
metrics, tactical models and recruitment logic. See
[ADR-0001](adr/0001-shared-platform-sport-modules.md).

| Sport | Intelligence focus | Competitors to study |
|---|---|---|
| Soccer | Passing networks, progressive actions, xG, pressing, roles, transfer valuation, tactical fit | Wyscout, StatsBomb |
| Cricket | Batter-vs-bowler matchups, pitch maps, wagon wheels, bowling variations, field placements, format-specific form | Cricket-21, NV Play |
| Basketball | Shot quality, spacing, lineups, possession efficiency, matchups, pick-and-roll coverage | Hudl, Instat |
| Baseball | Pitch quality, spin, velocity, expected outcomes, positioning, development | TrackMan, Rapsodo |
| American football | Formations, routes, coverages, blitzes, QB decisions, blocking, draft analysis | Hudl IQ |
| Ice hockey | Lines, shifts, shot quality, zone entries, coverage, goalie performance | Hudl Instat |
