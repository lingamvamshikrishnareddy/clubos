-- Stage 3: valuations, forecasts, tactical-fit recommendations and budget scenarios.
-- Every model output records the model run that produced it, and every model has a card.

begin;

create table model_runs (
  id            uuid primary key default gen_random_uuid(),
  model_name    text not null,  -- e.g. 'valuation_baseline'
  model_version text not null,
  sport_id      text references sports (id),
  trained_at    timestamptz not null default now(),
  -- Training data, validation results and known limits (the model card).
  card          jsonb not null default '{}',
  metrics       jsonb not null default '{}'  -- e.g. {"mae": ..., "interval_coverage": ...}
);

-- Public market data: transfers, trades, free-agent signings, auctions, extensions.
-- The valuation model learns from these (fee or annual salary, per the sport's valuation basis).
create table market_transactions (
  id            uuid primary key default gen_random_uuid(),
  player_id     uuid not null references players (id) on delete cascade,
  kind          text not null check (kind in ('transfer', 'loan', 'trade', 'free_agent_signing', 'auction', 'draft', 'contract_extension')),
  occurred_on   date not null,
  from_team_id  uuid references teams (id),
  to_team_id    uuid references teams (id),
  currency      char(3) not null,
  fee           numeric(14, 2),            -- null = undisclosed, not zero
  annual_salary numeric(14, 2),
  contract_years smallint,
  source_id     text not null references data_sources (id),
  source_record_id text not null,
  unique (source_id, source_record_id)
);

create index market_transactions_player_idx on market_transactions (player_id, occurred_on desc);

create table player_valuations (
  id           uuid primary key default gen_random_uuid(),
  player_id    uuid not null references players (id) on delete cascade,
  model_run_id uuid not null references model_runs (id),
  as_of        date not null,
  basis        text not null check (basis in ('transfer_fee', 'annual_salary')),
  currency     char(3) not null,
  value        numeric(14, 2) not null check (value >= 0),
  -- Prediction interval; recommendations always show the range, not just the point.
  value_low    numeric(14, 2) not null,
  value_high   numeric(14, 2) not null,
  drivers      jsonb not null default '[]',  -- [{"feature": "age", "effect": -0.12}, ...]
  check (value_low <= value and value <= value_high)
);

create index player_valuations_player_idx on player_valuations (player_id, as_of desc);

create table performance_forecasts (
  id            uuid primary key default gen_random_uuid(),
  player_id     uuid not null references players (id) on delete cascade,
  model_run_id  uuid not null references model_runs (id),
  season_label  text not null,  -- the season being forecast
  role_key      text,
  metric_key    text not null,
  forecast      numeric not null,
  forecast_low  numeric not null,
  forecast_high numeric not null,
  -- How much of the forecast comes from the player's own data vs the role average.
  evidence_weight numeric(4, 3) not null check (evidence_weight between 0 and 1),
  created_at    timestamptz not null default now(),
  unique (player_id, model_run_id, metric_key)
);

-- How a club wants a role played: weights over the sport's metric keys.
create table club_style_profiles (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  sport_id        text not null references sports (id),
  role_key        text not null,
  name            text not null,
  metric_weights  jsonb not null,  -- {"progressive_passes": 0.3, "tackles_won": 0.2, ...}
  updated_at      timestamptz not null default now(),
  unique (organisation_id, sport_id, role_key, name)
);

-- Contracts are used here for budget scenarios and in Stage 5 for squad operations.
create table contracts (
  id                  uuid primary key default gen_random_uuid(),
  organisation_id     uuid not null references organisations (id) on delete cascade,
  player_id           uuid not null references players (id),
  starts_on           date not null,
  ends_on             date not null,
  currency            char(3) not null,
  annual_salary       numeric(14, 2) not null check (annual_salary >= 0),
  signing_fee         numeric(14, 2) not null default 0,
  transfer_fee        numeric(14, 2) not null default 0,  -- amortised over the contract
  -- Bonuses, release clauses, options: [{"type": "release_clause", "amount": ...}]
  clauses             jsonb not null default '[]',
  status              text not null default 'active' check (status in ('draft', 'active', 'expired', 'terminated')),
  check (ends_on > starts_on)
);

create index contracts_org_idx on contracts (organisation_id, status);

create table recommendations (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id),
  role_key        text not null,
  style_profile_id uuid references club_style_profiles (id),
  model_run_id    uuid not null references model_runs (id),
  fit_score       numeric(5, 2) not null check (fit_score between 0 and 100),
  valuation_id    uuid references player_valuations (id),
  -- Why: [{"metric": "progressive_passes", "percentile": 91, "weight": 0.3}, ...]
  reasons         jsonb not null default '[]',
  evidence_clip_ids uuid[] not null default '{}',
  low_sample      boolean not null default false,
  status          text not null default 'new' check (status in ('new', 'reviewed', 'shortlisted', 'dismissed')),
  created_at      timestamptz not null default now()
);

create index recommendations_org_idx on recommendations (organisation_id, role_key, fit_score desc);

create table budget_scenarios (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  fiscal_year     integer not null,
  currency        char(3) not null,
  transfer_budget numeric(14, 2) not null,
  wage_budget     numeric(14, 2) not null,
  created_by      uuid references app_users (id),
  created_at      timestamptz not null default now()
);

create table budget_scenario_moves (
  id            uuid primary key default gen_random_uuid(),
  scenario_id   uuid not null references budget_scenarios (id) on delete cascade,
  player_id     uuid not null references players (id),
  direction     text not null check (direction in ('in', 'out', 'renew')),
  transfer_fee  numeric(14, 2) not null default 0,  -- paid (in) or received (out)
  annual_salary numeric(14, 2) not null default 0,
  contract_years smallint not null default 1 check (contract_years between 1 and 10)
);

commit;
