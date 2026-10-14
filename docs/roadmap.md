# Roadmap

Each stage is a GitHub milestone, created by the *Bootstrap labels and milestones* workflow.
The **data and model foundation** for every stage is in place for all six sports. The main
remaining work is the **API and web app** that put it in front of club staff.

| Stage | Foundation built | Remaining |
|---|---|---|
| 1 – Recruitment core | Player database with provenance and identity; StatsBomb connector (stats, passes, shots); season stats; like-for-like role comparison; scouting reports; shortlists; squad depth analysis | API, web screens, CSV import, identity review queue |
| 2 – Video and match evidence | Videos, tagged events using each sport's tag vocabulary, clips, playlists, clips as scouting evidence, tactical reports; play-by-play for all six sports; passing networks, formation detection, shot charts, lineups and line combinations, cricket matchups, wagon wheels and pitch maps, baseball pitch mix, American football play efficiency | Video upload and storage, player UI, automatic tagging (computer vision) |
| 3 – Connected decisions | Market data; valuation model with ranges and drivers; performance forecasts; club style profiles; tactical-fit recommendations with reasons and clips; contracts; budget scenarios | Recommendation and scenario UI; league-strength adjustment |
| 4 – Development and availability | Training sessions and session RPE load; sport-specific external load; wellness; availability with medical records restricted to medical staff (row-level security); development goals; assessments; workload indicators; generated player reports | Player check-in app, wearable connectors |
| 5 – Squad operations | Staff profiles, calendar, attendance, tasks, announcements, direct messaging, academy registrations, guardians and renewals, facilities with double-booking prevention, payroll runs and payslips | Scheduling UI, notifications |
| 6 – Commercial operations | Budgets, transactions, sponsors and deals, advertising inventory and bookings, stadium events, academy fees and payments; full-year financial forecasts and three-year plans with committed wages and sponsorship; executive views (wage bill, squad value, budget vs actual, revenue by stream, cost per player, club and player performance ROI); decisions with outcome reviews | Executive dashboards, accounting export |
| 7 – Additional sports and real leagues | Soccer, American football, baseball, basketball, ice hockey, cricket; real league structures and rules (NFL, NBA, IPL, Premier League, EFL); real data for the NFL (nflverse), IPL (Cricsheet) and StatsBomb competitions | Licensed data for the NBA and EFL; MLB and NHL connectors |

## Next up

1. **API:** auth, organisations and roles, connecting as `clubos_app` so the row-level security policies apply.
2. **Web app:** player search and comparison, recommendations, squad depth, budget scenarios, executive dashboard.
3. **Real data for the other sports:** licensed or open data sources, each reviewed with the *Data source request* template.
