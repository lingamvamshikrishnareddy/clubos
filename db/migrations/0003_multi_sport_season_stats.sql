-- Multi-sport support: sport-specific competition attributes, season-level stats for
-- comparisons and recruitment, and a source for fictional demo data.

begin;

-- e.g. cricket {"format": "T20"}, basketball {"quarter_minutes": 12}
alter table competitions add column attributes jsonb not null default '{}';

-- Teams belonging to a club (first team, reserves, academy age groups).
alter table teams add column organisation_id uuid references organisations (id) on delete set null;

insert into data_sources (id, name, licence, attribution, url) values
  ('mock', 'Fictional demo data', 'Generated; not real people or results', 'Fictional demo data', null);

-- One row per player, team and season. Exposure is in the unit the sport module defines
-- for the player's role (minutes, snaps, plate appearances, balls faced...).
create table player_season_stats (
  id               uuid primary key default gen_random_uuid(),
  player_id        uuid not null references players (id) on delete cascade,
  season_id        uuid not null references seasons (id),
  team_id          uuid not null references teams (id),
  role_key         text,
  exposure         numeric(10, 1),  -- null = unknown, not zero
  exposure_unit    text not null,
  appearances      integer,
  source_id        text not null references data_sources (id),
  source_record_id text not null,
  ingestion_run_id uuid references ingestion_runs (id),
  ingested_at      timestamptz not null default now(),
  unique (player_id, season_id, team_id, source_id)
);

create index player_season_stats_season_idx on player_season_stats (season_id, role_key);

-- Sums for per-exposure and total metrics; the season value for rate metrics.
create table player_season_metric_values (
  season_stats_id uuid not null references player_season_stats (id) on delete cascade,
  metric_key      text not null,
  value           numeric,
  primary key (season_stats_id, metric_key)
);

commit;
