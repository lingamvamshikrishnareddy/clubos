# ADR-0004: Access control in Postgres row-level security

Status: accepted

## Context

Clubs share one database. Their recruitment plans, finances and players' medical information
must never leak to another club, or to staff inside a club who have no reason to see them.
Medical permissions in particular were a stated requirement. Checks written only in API code
are easy to miss on one endpoint.

## Decision

- **Policies in the database.** The API connects as role `clubos_app` and sets `app.user_id` at the start of each request transaction. Postgres row-level security then enforces access on every query (migration `0011`).
- **Club-private data.** Every table with an `organisation_id`, and every table that hangs off one, is visible only to that organisation's members.
- **Medical records.** Only the organisation's `medical` and `admin` roles can see them. Everyone else sees availability status and reason category only.
- **Contracts, payroll, transactions, budgets, forecasts and plans.** Restricted to finance, executive and admin roles; the sporting director also sees contracts, budgets, forecasts and plans. Staff salaries are visible to finance roles and to the staff member themselves.
- **Messages.** Readable only by thread participants.
- **Shared reference data.** Competitions, matches, players, season stats, market data and league-wide model outputs are readable by every signed-in user.
- **Views.** All views run as `security_invoker`, so policies apply through them.
- **Batch jobs.** Migrations, ingestion and model jobs run as the table owner and are not subject to these policies.

## Consequences

- **Tests.** `db/tests/rls.sql` checks the rules with two clubs and staff in different roles, and runs in CI.
- **Policy recursion.** Policies that reference other protected tables use `security definer` helper functions, to avoid recursive policy evaluation.
- **New tables and views.** Each new club-private table needs a policy and a test case. New views must use `security_invoker`.
