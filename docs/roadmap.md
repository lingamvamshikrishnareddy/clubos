# Roadmap

Each stage is a GitHub milestone, created by the *Bootstrap labels and milestones* workflow.
The **data and model foundation** for every stage is in place for all six sports. The main
remaining work is the **API and web app** that put it in front of club staff.

| Stage | Foundation built | Remaining |
|---|---|---|
| 1 – Recruitment core | Player database with provenance and identity; StatsBomb connector; season stats; like-for-like role comparison; scouting reports; shortlists; squad depth analysis | API, web screens, CSV import, identity review queue |
| 2 – Video and match evidence | Videos, tagged events using each sport's tag vocabulary, clips, playlists, clips as scouting evidence, tactical reports | Video upload and storage, player UI, automatic tagging (computer vision) |
| 3 – Connected decisions | Market data; valuation model with ranges and drivers; performance forecasts; club style profiles; tactical-fit recommendations with reasons and clips; contracts; budget scenarios | Recommendation and scenario UI; league-strength adjustment |
| 4 – Development and availability | Training sessions and session RPE load; sport-specific external load; wellness; availability with separate medical records; development goals; assessments; workload indicators | Player check-in app, medical permissions (RLS), wearable connectors |
| 5 – Squad operations | Staff profiles, calendar, attendance, tasks, announcements, academy registrations and guardians, facilities with double-booking prevention | Scheduling UI, notifications |
| 6 – Commercial operations | Budgets, transactions, sponsors and deals, advertising inventory and bookings, stadium events, academy fees and payments; executive views (wage bill, squad value, budget vs actual, revenue by stream, cost per player) | Executive dashboards, accounting export |
| 7 – Additional sports | Soccer, American football, baseball, basketball, ice hockey, cricket | Real-data connectors for the five non-soccer sports |

## Next up

1. **API:** auth, organisations, roles and row-level security, including medical-only access to `medical_records`.
2. **Web app:** player search and comparison, recommendations, squad depth, budget scenarios, executive dashboard.
3. **Real data for the other sports:** licensed or open data sources, each reviewed with the *Data source request* template.
