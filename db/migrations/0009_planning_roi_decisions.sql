-- Executive financial planning, performance ROI, academy renewals, payroll, decision
-- outcomes and generated player reports.

begin;

-- ---------------------------------------------------------------------------
-- Financial forecasts and multi-year plans (written by services/ml)
-- ---------------------------------------------------------------------------

-- Full-year projection per budget category: actual to date + projected remainder.
create table financial_forecasts (
  id                  uuid primary key default gen_random_uuid(),
  organisation_id     uuid not null references organisations (id) on delete cascade,
  model_run_id        uuid not null references model_runs (id),
  as_of               date not null,
  fiscal_year         integer not null,
  category            text not null,
  currency            char(3) not null,
  actual_to_date      numeric(16, 2) not null,
  projected_remaining numeric(16, 2) not null,
  projected_full_year numeric(16, 2) not null,
  projected_low       numeric(16, 2) not null,
  projected_high      numeric(16, 2) not null,
  budget              numeric(16, 2),  -- null when the category has no budget line
  -- 'contracted' when driven by contracts and deals, 'run_rate' when extrapolated.
  basis               text not null check (basis in ('contracted', 'run_rate', 'mixed')),
  unique (organisation_id, model_run_id, fiscal_year, category)
);

create table financial_plans (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  model_run_id    uuid references model_runs (id),
  name            text not null,
  first_year      integer not null,
  years           smallint not null check (years between 1 and 10),
  currency        char(3) not null,
  -- e.g. {"wage_inflation": 0.04, "commercial_growth": 0.05}
  assumptions     jsonb not null default '{}',
  created_at      timestamptz not null default now()
);

create table financial_plan_lines (
  plan_id     uuid not null references financial_plans (id) on delete cascade,
  fiscal_year integer not null,
  category    text not null,
  -- Signed like financial_transactions: income positive, costs negative.
  amount      numeric(16, 2) not null,
  committed   numeric(16, 2) not null default 0,  -- part already under contract
  primary key (plan_id, fiscal_year, category)
);

-- Wages already committed by contracts, per future fiscal year (pro rata by days).
create view v_wage_commitments_by_year as
select c.organisation_id, c.currency, y.fiscal_year,
       round(sum(c.annual_salary * (least(c.ends_on, make_date(y.fiscal_year, 12, 31))
                                    - greatest(c.starts_on, make_date(y.fiscal_year, 1, 1)) + 1) / 365.0), 2) as committed_wages,
       count(distinct c.player_id) as players_under_contract
from contracts c
cross join lateral generate_series(extract(year from c.starts_on)::int, extract(year from c.ends_on)::int) as y(fiscal_year)
where c.status = 'active'
group by c.organisation_id, c.currency, y.fiscal_year;

-- Sponsorship income already contracted, per fiscal year (pro rata by days).
create view v_sponsorship_commitments_by_year as
select s.organisation_id, d.currency, y.fiscal_year,
       round(sum(d.annual_value * (least(d.ends_on, make_date(y.fiscal_year, 12, 31))
                                   - greatest(d.starts_on, make_date(y.fiscal_year, 1, 1)) + 1) / 365.0), 2) as committed_income,
       count(*) as deals
from sponsorship_deals d
join sponsors s on s.id = d.sponsor_id
cross join lateral generate_series(extract(year from d.starts_on)::int, extract(year from d.ends_on)::int) as y(fiscal_year)
where d.status = 'active'
group by s.organisation_id, d.currency, y.fiscal_year;

-- ---------------------------------------------------------------------------
-- Payroll
-- ---------------------------------------------------------------------------

create table payroll_runs (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  period_start    date not null,
  period_end      date not null,
  currency        char(3) not null,
  status          text not null default 'draft' check (status in ('draft', 'approved', 'paid')),
  approved_by     uuid references app_users (id),
  paid_on         date,
  unique (organisation_id, period_start),
  check (period_end >= period_start)
);

-- One payslip per player or staff member per run. Gross only: tax and statutory
-- deductions are left to the club's payroll provider.
create table payslips (
  id             uuid primary key default gen_random_uuid(),
  payroll_run_id uuid not null references payroll_runs (id) on delete cascade,
  player_id      uuid references players (id),
  user_id        uuid references app_users (id),
  contract_id    uuid references contracts (id),
  basic_pay      numeric(14, 2) not null,
  bonuses        numeric(14, 2) not null default 0,
  -- e.g. [{"type": "appearance_bonus", "count": 3, "amount": 4500}]
  bonus_detail   jsonb not null default '[]',
  gross_pay      numeric(14, 2) generated always as (basic_pay + bonuses) stored,
  check ((player_id is null) <> (user_id is null))
);

create index payslips_run_idx on payslips (payroll_run_id);

-- ---------------------------------------------------------------------------
-- Performance ROI
-- ---------------------------------------------------------------------------

-- Role performance score per player-season (mean direction-aware percentile of the
-- role's comparison metrics), written by services/ml.
create table player_performance_scores (
  player_id    uuid not null references players (id) on delete cascade,
  season_id    uuid not null references seasons (id),
  model_run_id uuid not null references model_runs (id),
  role_key     text not null,
  score        numeric(5, 2) not null check (score between 0 and 100),
  low_sample   boolean not null,
  percentiles  jsonb not null,  -- {"metric_key": percentile}
  primary key (player_id, season_id, model_run_id)
);

create view v_latest_performance_scores as
select distinct on (s.player_id) s.player_id, s.season_id, se.label as season_label, s.role_key, s.score, s.low_sample
from player_performance_scores s
join seasons se on se.id = s.season_id
join model_runs r on r.id = s.model_run_id
order by s.player_id, se.starts_on desc nulls last, r.trained_at desc;

-- Team results per season for the club's own teams.
create view v_team_results as
select t.organisation_id, t.id as team_id, m.season_id, se.label as season_label,
       count(*) as games,
       count(*) filter (where (m.home_team_id = t.id and m.home_score > m.away_score)
                           or (m.away_team_id = t.id and m.away_score > m.home_score)) as wins,
       count(*) filter (where m.home_score = m.away_score) as draws,
       count(*) filter (where (m.home_team_id = t.id and m.home_score < m.away_score)
                           or (m.away_team_id = t.id and m.away_score < m.home_score)) as losses,
       sum(case when m.home_team_id = t.id then m.home_score else m.away_score end) as scored,
       sum(case when m.home_team_id = t.id then m.away_score else m.home_score end) as conceded
from teams t
join matches m on t.id in (m.home_team_id, m.away_team_id)
join seasons se on se.id = m.season_id
where t.organisation_id is not null and m.home_score is not null and m.away_score is not null
group by t.organisation_id, t.id, m.season_id, se.label;

-- Club-level ROI: what current squad costs per win and per point of goal/run difference.
create view v_club_performance_roi as
select r.organisation_id, r.season_label, r.games, r.wins, r.draws, r.losses,
       round(r.wins::numeric / nullif(r.games, 0), 3) as win_rate,
       r.scored - r.conceded as score_difference,
       w.currency, w.annual_cost_incl_amortisation as squad_annual_cost,
       round(w.annual_cost_incl_amortisation / nullif(r.wins, 0), 2) as cost_per_win
from v_team_results r
join v_wage_bill w on w.organisation_id = r.organisation_id;

-- Player-level value for money: annual cost against role performance score.
create view v_player_performance_roi as
select c.organisation_id, c.player_id, p.full_name, s.role_key, s.season_label, s.score as performance_score,
       s.low_sample, c.currency, c.annual_cost,
       round(c.annual_cost / nullif(s.score, 0), 2) as cost_per_score_point,
       v.value as market_value, v.value_low as market_value_low, v.value_high as market_value_high
from v_player_contract_costs c
join players p on p.id = c.player_id
left join v_latest_performance_scores s on s.player_id = c.player_id
left join v_latest_valuations v on v.player_id = c.player_id;

-- ---------------------------------------------------------------------------
-- Academy renewals
-- ---------------------------------------------------------------------------

create table academy_renewals (
  id                uuid primary key default gen_random_uuid(),
  registration_id   uuid not null references academy_registrations (id) on delete cascade,
  next_season_label text not null,
  offered_on        date not null,
  respond_by        date not null,
  currency          char(3) not null,
  annual_fee        numeric(14, 2) not null check (annual_fee >= 0),
  status            text not null default 'offered' check (status in ('offered', 'accepted', 'declined', 'lapsed', 'not_offered')),
  responded_on      date,
  notes             text,
  unique (registration_id, next_season_label)
);

create view v_academy_renewals_due as
select r.organisation_id, a.id as renewal_id, p.full_name, a.next_season_label, a.respond_by, a.status,
       a.currency, a.annual_fee,
       (select count(*) from academy_fees f where f.registration_id = r.id and f.status = 'overdue') as overdue_fees
from academy_renewals a
join academy_registrations r on r.id = a.registration_id
join players p on p.id = r.player_id
where a.status = 'offered';

-- ---------------------------------------------------------------------------
-- Decisions and outcomes: closing the loop on recommendations
-- ---------------------------------------------------------------------------

create table decisions (
  id                uuid primary key default gen_random_uuid(),
  organisation_id   uuid not null references organisations (id) on delete cascade,
  kind              text not null check (kind in ('signing', 'sale', 'renewal', 'release', 'selection', 'tactical', 'training', 'return_to_play', 'commercial', 'other')),
  title             text not null,
  player_id         uuid references players (id),
  recommendation_id uuid references recommendations (id) on delete set null,
  scenario_id       uuid references budget_scenarios (id) on delete set null,
  decided_on        date not null,
  decided_by        uuid references app_users (id),
  rationale         text not null,
  -- What success looks like, e.g. {"metric": "np_xg", "target": 0.45, "by": "2027-05-31"}
  expected_outcome  jsonb not null default '{}',
  review_on         date,
  status            text not null default 'open' check (status in ('open', 'reviewed', 'withdrawn'))
);

create index decisions_org_idx on decisions (organisation_id, decided_on desc);

create table decision_outcomes (
  id          uuid primary key default gen_random_uuid(),
  decision_id uuid not null references decisions (id) on delete cascade,
  reviewed_on date not null,
  reviewer_id uuid references app_users (id),
  rating      smallint not null check (rating between 1 and 5),  -- 1 = much worse than expected, 5 = much better
  actual      jsonb not null default '{}',
  lessons     text
);

-- How recommendations that led to decisions turned out, per model.
create view v_recommendation_outcomes as
select r.organisation_id, mr.model_name, mr.model_version, count(distinct d.id) as decisions,
       count(o.id) as reviewed, round(avg(o.rating), 2) as average_rating,
       count(o.id) filter (where o.rating >= 4) as better_than_expected,
       count(o.id) filter (where o.rating <= 2) as worse_than_expected
from decisions d
join recommendations r on r.id = d.recommendation_id
join model_runs mr on mr.id = r.model_run_id
left join decision_outcomes o on o.decision_id = d.id
group by r.organisation_id, mr.model_name, mr.model_version;

-- ---------------------------------------------------------------------------
-- Generated player performance reports
-- ---------------------------------------------------------------------------

create table player_reports (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id) on delete cascade,
  model_run_id    uuid not null references model_runs (id),
  period_start    date not null,
  period_end      date not null,
  generated_at    timestamptz not null default now(),
  summary         text not null,
  -- [{"title": "Season performance", "items": [...]}, ...] each item carrying its source table.
  sections        jsonb not null
);

create index player_reports_player_idx on player_reports (player_id, generated_at desc);

-- ---------------------------------------------------------------------------
-- Direct messaging between staff (and players with accounts)
-- ---------------------------------------------------------------------------

create table message_threads (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  subject         text not null,
  player_id       uuid references players (id),  -- optional context, e.g. a recruitment target
  created_by      uuid references app_users (id),
  created_at      timestamptz not null default now()
);

create table message_participants (
  thread_id    uuid not null references message_threads (id) on delete cascade,
  user_id      uuid not null references app_users (id) on delete cascade,
  last_read_at timestamptz,
  primary key (thread_id, user_id)
);

create table messages (
  id        uuid primary key default gen_random_uuid(),
  thread_id uuid not null references message_threads (id) on delete cascade,
  sender_id uuid not null references app_users (id),
  body      text not null,
  sent_at   timestamptz not null default now()
);

create index messages_thread_idx on messages (thread_id, sent_at);

commit;
