-- Stage 1: shared core, data provenance, player identity and recruitment workflow.
-- See docs/adr/0001-shared-platform-sport-modules.md and docs/adr/0002-data-provenance-and-identity.md.

begin;

-- ---------------------------------------------------------------------------
-- Platform: sports, clubs, staff
-- ---------------------------------------------------------------------------

create table sports (
  id   text primary key,
  name text not null
);

insert into sports (id, name) values
  ('soccer', 'Association football'),
  ('american_football', 'American football'),
  ('baseball', 'Baseball'),
  ('basketball', 'Basketball'),
  ('ice_hockey', 'Ice hockey'),
  ('cricket', 'Cricket');

create table organisations (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  primary_sport text not null references sports (id),
  created_at    timestamptz not null default now()
);

create table app_users (
  id           uuid primary key default gen_random_uuid(),
  email        text not null unique,
  display_name text not null,
  created_at   timestamptz not null default now()
);

create type staff_role as enum (
  'admin', 'sporting_director', 'head_coach', 'analyst', 'scout',
  'performance', 'medical', 'finance', 'executive'
);

create table memberships (
  organisation_id uuid not null references organisations (id) on delete cascade,
  user_id         uuid not null references app_users (id) on delete cascade,
  role            staff_role not null,
  primary key (organisation_id, user_id, role)
);

-- ---------------------------------------------------------------------------
-- Provenance: every imported fact points back to a source and an ingestion run
-- ---------------------------------------------------------------------------

create table data_sources (
  id          text primary key,
  name        text not null,
  licence     text not null,
  attribution text,
  url         text
);

insert into data_sources (id, name, licence, attribution, url) values
  ('statsbomb_open_data', 'StatsBomb Open Data', 'StatsBomb public data user agreement',
   'Data provided by StatsBomb', 'https://github.com/statsbomb/open-data'),
  ('manual', 'Manual entry by club staff', 'Club-owned', null, null);

create table ingestion_runs (
  id               uuid primary key default gen_random_uuid(),
  source_id        text not null references data_sources (id),
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  status           text not null default 'running' check (status in ('running', 'succeeded', 'failed')),
  records_ingested integer not null default 0,
  notes            text
);

-- ---------------------------------------------------------------------------
-- Competition context
-- ---------------------------------------------------------------------------

create table competitions (
  id       uuid primary key default gen_random_uuid(),
  sport_id text not null references sports (id),
  name     text not null,
  country  text,
  gender   text check (gender in ('men', 'women', 'mixed')),
  -- Relative strength tier used to adjust cross-league comparisons; null = unknown.
  tier     smallint check (tier > 0),
  is_youth boolean not null default false
);

create table seasons (
  id             uuid primary key default gen_random_uuid(),
  competition_id uuid not null references competitions (id),
  label          text not null,
  starts_on      date,
  ends_on        date,
  unique (competition_id, label)
);

create table teams (
  id       uuid primary key default gen_random_uuid(),
  sport_id text not null references sports (id),
  name     text not null,
  country  text
);

create table matches (
  id           uuid primary key default gen_random_uuid(),
  season_id    uuid not null references seasons (id),
  home_team_id uuid not null references teams (id),
  away_team_id uuid not null references teams (id),
  kickoff_at   timestamptz,
  home_score   smallint,
  away_score   smallint,
  check (home_team_id <> away_team_id)
);

create index matches_season_idx on matches (season_id);

-- ---------------------------------------------------------------------------
-- Players and identity resolution
-- ---------------------------------------------------------------------------

create table players (
  id           uuid primary key default gen_random_uuid(),
  sport_id     text not null references sports (id),
  full_name    text not null,
  known_as     text,
  birth_date   date,
  nationality  text,
  primary_role text,  -- a role key from the sport module, e.g. 'full_back'
  -- Sport-specific attributes (preferred foot, batting hand, shoots left/right...).
  attributes   jsonb not null default '{}',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index players_name_idx on players (sport_id, lower(full_name));

-- One internal player, many provider IDs. Probabilistic matches stay unverified
-- until a person confirms them.
create table player_identities (
  source_id    text not null references data_sources (id),
  external_id  text not null,
  player_id    uuid not null references players (id) on delete cascade,
  match_method text not null check (match_method in ('exact', 'probabilistic', 'manual')),
  confidence   numeric(4, 3) not null check (confidence between 0 and 1),
  verified_by  uuid references app_users (id),
  created_at   timestamptz not null default now(),
  primary key (source_id, external_id)
);

create index player_identities_player_idx on player_identities (player_id);

-- ---------------------------------------------------------------------------
-- Performance data
-- ---------------------------------------------------------------------------

create table player_match_appearances (
  id               uuid primary key default gen_random_uuid(),
  player_id        uuid not null references players (id),
  match_id         uuid not null references matches (id),
  team_id          uuid not null references teams (id),
  role_key         text,
  minutes          numeric(5, 1),  -- null = unknown, not zero
  source_id        text not null references data_sources (id),
  source_record_id text not null,
  ingestion_run_id uuid references ingestion_runs (id),
  ingested_at      timestamptz not null default now(),
  unique (player_id, match_id, source_id)
);

create index appearances_player_idx on player_match_appearances (player_id);

-- A missing row means the source did not provide the metric; a null value means it
-- provided the field without a value. Neither is ever read as zero.
create table player_metric_values (
  appearance_id uuid not null references player_match_appearances (id) on delete cascade,
  metric_key    text not null,  -- a metric key from the sport module
  value         numeric,
  primary key (appearance_id, metric_key)
);

-- ---------------------------------------------------------------------------
-- Recruitment workflow (club-private)
-- ---------------------------------------------------------------------------

create table scouting_reports (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id),
  author_id       uuid not null references app_users (id),
  match_id        uuid references matches (id),
  role_assessed   text,
  rating          smallint check (rating between 1 and 10),
  summary         text not null,
  strengths       text,
  weaknesses      text,
  recommendation  text not null check (recommendation in ('sign', 'monitor', 'reject')),
  created_at      timestamptz not null default now()
);

create index scouting_reports_player_idx on scouting_reports (organisation_id, player_id);

create table shortlists (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  role_key        text,
  created_by      uuid not null references app_users (id),
  created_at      timestamptz not null default now()
);

create type shortlist_stage as enum ('watch', 'scout', 'shortlist', 'approach', 'signed', 'rejected');

create table shortlist_entries (
  shortlist_id uuid not null references shortlists (id) on delete cascade,
  player_id    uuid not null references players (id),
  stage        shortlist_stage not null default 'watch',
  notes        text,
  added_by     uuid not null references app_users (id),
  added_at     timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  primary key (shortlist_id, player_id)
);

-- Lightweight squad view so recruitment can show squad-fit gaps (full squad ops is Stage 5).
create type squad_status as enum ('first_team', 'reserve', 'academy', 'loaned_out');

create table squad_members (
  organisation_id     uuid not null references organisations (id) on delete cascade,
  player_id           uuid not null references players (id),
  role_key            text,
  status              squad_status not null,
  contract_expires_on date,
  joined_on           date,
  left_on             date,
  primary key (organisation_id, player_id)
);

create table audit_log (
  id              bigint generated always as identity primary key,
  organisation_id uuid references organisations (id),
  actor_id        uuid references app_users (id),
  action          text not null,
  entity          text not null,
  entity_id       text,
  at              timestamptz not null default now(),
  details         jsonb not null default '{}'
);

commit;
