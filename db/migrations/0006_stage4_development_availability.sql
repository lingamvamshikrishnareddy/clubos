-- Stage 4: training load, wellness, development goals, assessments and availability.
--
-- Risk indicators are decision support for qualified medical and performance staff.
-- They never diagnose an injury or predict that a player will stay injury-free.
-- Medical details are kept apart from availability so most staff see status, not cause.

begin;

create table training_sessions (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  team_id         uuid references teams (id),
  starts_at       timestamptz not null,
  duration_minutes integer not null check (duration_minutes > 0),
  kind            text not null check (kind in ('training', 'match', 'recovery', 'gym', 'rehab')),
  focus           text,
  planned_intensity text check (planned_intensity in ('low', 'moderate', 'high'))
);

create index training_sessions_org_idx on training_sessions (organisation_id, starts_at);

-- Internal load uses session RPE (rating of perceived exertion, 0–10) × minutes.
create table session_loads (
  session_id      uuid not null references training_sessions (id) on delete cascade,
  player_id       uuid not null references players (id),
  participated    boolean not null default true,
  minutes         integer check (minutes >= 0),
  rpe             numeric(3, 1) check (rpe between 0 and 10),
  session_load    numeric(8, 1) generated always as (minutes * rpe) stored,
  -- Sport-specific external load, e.g. {"distance_m": 9800, "high_speed_m": 650} or
  -- {"pitches": 92} or {"overs_bowled": 8}.
  external_load   jsonb not null default '{}',
  primary key (session_id, player_id)
);

create table wellness_checkins (
  player_id      uuid not null references players (id) on delete cascade,
  checkin_date   date not null,
  sleep_hours    numeric(3, 1) check (sleep_hours between 0 and 24),
  sleep_quality  smallint check (sleep_quality between 1 and 5),
  fatigue        smallint check (fatigue between 1 and 5),  -- 5 = very fresh
  soreness       smallint check (soreness between 1 and 5), -- 5 = no soreness
  mood           smallint check (mood between 1 and 5),
  stress         smallint check (stress between 1 and 5),   -- 5 = very relaxed
  primary key (player_id, checkin_date)
);

-- Computed indicators (e.g. acute:chronic workload ratio). Wording shown to staff is
-- "indicator", with the inputs, never "injury risk score".
create table workload_indicators (
  id             uuid primary key default gen_random_uuid(),
  player_id      uuid not null references players (id) on delete cascade,
  model_run_id   uuid references model_runs (id),
  as_of          date not null,
  acute_load     numeric(10, 1),
  chronic_load   numeric(10, 1),
  acwr           numeric(5, 2),
  monotony       numeric(5, 2),
  wellness_score numeric(4, 2),
  flags          text[] not null default '{}',  -- e.g. {'load_spike', 'low_wellness'}
  unique (player_id, as_of)
);

create table availability_status (
  id          uuid primary key default gen_random_uuid(),
  player_id   uuid not null references players (id) on delete cascade,
  organisation_id uuid not null references organisations (id) on delete cascade,
  status      text not null check (status in ('available', 'modified_training', 'unavailable')),
  starts_on   date not null,
  expected_return_on date,
  ends_on     date,
  -- Visible to all staff; clinical detail lives in medical_records.
  reason_category text check (reason_category in ('injury', 'illness', 'personal', 'suspension', 'international_duty', 'load_management', 'other')),
  set_by      uuid references app_users (id),
  created_at  timestamptz not null default now()
);

create index availability_player_idx on availability_status (player_id, starts_on desc);

-- Restricted to medical staff (enforced by the API and row-level security).
create table medical_records (
  id              uuid primary key default gen_random_uuid(),
  availability_id uuid not null references availability_status (id) on delete cascade,
  body_area       text,
  diagnosis       text,
  treatment_plan  text,
  recorded_by     uuid references app_users (id),
  recorded_at     timestamptz not null default now()
);

create table development_goals (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id) on delete cascade,
  title           text not null,
  metric_key      text,  -- optional link to a sport metric
  baseline        numeric,
  target          numeric,
  due_on          date,
  status          text not null default 'active' check (status in ('active', 'achieved', 'missed', 'dropped')),
  owner_id        uuid references app_users (id),
  created_at      timestamptz not null default now()
);

create table assessments (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id) on delete cascade,
  assessed_on     date not null,
  kind            text not null check (kind in ('physical', 'technical', 'tactical', 'psychological', 'medical_screening')),
  -- Test results, e.g. {"sprint_30m_s": 4.1, "cmj_cm": 41}
  results         jsonb not null default '{}',
  notes           text,
  assessor_id     uuid references app_users (id)
);

create index assessments_player_idx on assessments (player_id, assessed_on desc);

commit;
