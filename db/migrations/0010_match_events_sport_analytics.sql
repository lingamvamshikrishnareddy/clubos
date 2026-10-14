-- Detailed match events for every sport, on-field shifts, and the sport-specific
-- analytics built on them: passing networks, formations, shot charts, lineups and line
-- combinations, cricket matchups, wagon wheels and pitch maps, baseball pitch mix,
-- American football play efficiency.

begin;

-- One row per event. event_type is a key from the sport module's eventTypes; attribute
-- values use its videoTags vocabulary where one exists.
--   soccer pass:          player = passer,  related_player = receiver
--   cricket delivery:     player = bowler,  related_player = batter
--   baseball pitch:       player = pitcher, related_player = batter
--   American football:    player = passer or ball carrier, related_player = target
--   basketball/hockey:    player = shooter, related_player = assister
-- Coordinates are normalised to 0–100 on both axes, with the team attacking towards x = 100.
-- Cricket: x = line (0 = wide off side, 100 = wide leg side), y = length (0 = yorker,
-- 100 = short); end_x/end_y = where the ball was hit (wagon wheel, batter at 50,50).
create table match_events (
  id                uuid primary key default gen_random_uuid(),
  match_id          uuid not null references matches (id) on delete cascade,
  source_id         text not null references data_sources (id),
  source_record_id  text not null,
  sequence          integer not null,
  period            smallint not null,
  clock_seconds     numeric(8, 1),
  team_id           uuid references teams (id),
  player_id         uuid references players (id),
  related_player_id uuid references players (id),
  event_type        text not null,
  outcome           text,
  x                 numeric(5, 2) check (x between 0 and 100),
  y                 numeric(5, 2) check (y between 0 and 100),
  end_x             numeric(5, 2) check (end_x between 0 and 100),
  end_y             numeric(5, 2) check (end_y between 0 and 100),
  value             numeric(8, 3),  -- xG, runs, points or yards, per event type
  attributes        jsonb not null default '{}',
  unique (source_id, source_record_id)
);

create index match_events_match_idx on match_events (match_id, sequence);
create index match_events_player_idx on match_events (player_id, event_type);
create index match_events_related_idx on match_events (related_player_id, event_type);

-- Time on court or ice, used for lineups (basketball) and line combinations (hockey).
create table player_shifts (
  match_id      uuid not null references matches (id) on delete cascade,
  player_id     uuid not null references players (id),
  team_id       uuid not null references teams (id),
  period        smallint not null,
  start_seconds numeric(8, 1) not null,
  end_seconds   numeric(8, 1) not null,
  source_id     text not null references data_sources (id),
  check (end_seconds > start_seconds),
  primary key (match_id, player_id, period, start_seconds)
);

-- Written by services/ml: performance of player combinations while on together.
create table unit_stats (
  id               uuid primary key default gen_random_uuid(),
  model_run_id     uuid not null references model_runs (id),
  team_id          uuid not null references teams (id),
  season_id        uuid references seasons (id),
  unit_kind        text not null check (unit_kind in ('lineup', 'forward_line', 'defence_pair')),
  player_ids       uuid[] not null,
  seconds_together numeric(10, 1) not null,
  value_for        numeric(10, 3) not null,
  value_against    numeric(10, 3) not null,
  value_kind       text not null,  -- 'points', 'goals', 'xg'
  matches          integer not null
);

create index unit_stats_team_idx on unit_stats (team_id, unit_kind);

-- Written by services/ml: shape detected from players' average positions.
create table formation_detections (
  match_id          uuid not null references matches (id) on delete cascade,
  team_id           uuid not null references teams (id),
  model_run_id      uuid not null references model_runs (id),
  formation         text not null,
  -- [{"player_id": ..., "x": 41.2, "y": 63.0, "line": 1}]
  average_positions jsonb not null,
  confidence        numeric(4, 3) not null check (confidence between 0 and 1),
  primary key (match_id, team_id, model_run_id)
);

-- ---------------------------------------------------------------------------
-- Soccer
-- ---------------------------------------------------------------------------

create view v_passing_network as
select e.match_id, e.team_id, e.player_id as passer_id, e.related_player_id as receiver_id,
       count(*) as passes,
       round(avg(e.x), 1) as avg_start_x, round(avg(e.y), 1) as avg_start_y
from match_events e
join players p on p.id = e.player_id and p.sport_id = 'soccer'
where e.event_type = 'pass' and e.outcome = 'complete' and e.related_player_id is not null
group by e.match_id, e.team_id, e.player_id, e.related_player_id;

create view v_average_positions as
select e.match_id, e.team_id, e.player_id, count(*) as events,
       round(avg(e.x), 1) as avg_x, round(avg(e.y), 1) as avg_y
from match_events e
where e.player_id is not null and e.x is not null
group by e.match_id, e.team_id, e.player_id;

-- ---------------------------------------------------------------------------
-- Shot charts (soccer, basketball, ice hockey)
-- ---------------------------------------------------------------------------

create view v_shot_chart as
select e.match_id, e.team_id, e.player_id, p.sport_id, e.x, e.y, e.outcome,
       e.value, e.attributes ->> 'shot_zone' as shot_zone, e.attributes ->> 'shot_danger' as shot_danger
from match_events e
join players p on p.id = e.player_id
where e.event_type = 'shot';

-- ---------------------------------------------------------------------------
-- Cricket
-- ---------------------------------------------------------------------------

create view v_cricket_deliveries as
select e.match_id, e.period as innings, (e.attributes ->> 'over')::int as over_number,
       (e.attributes ->> 'ball')::int as ball, e.player_id as bowler_id, e.related_player_id as batter_id,
       coalesce((e.attributes ->> 'runs_bat')::int, 0) as runs_bat,
       coalesce((e.attributes ->> 'extras')::int, 0) as extras,
       e.attributes ->> 'extra_type' as extra_type,
       e.outcome = 'wicket' as wicket, e.attributes ->> 'dismissal' as dismissal,
       e.attributes ->> 'length' as length, e.attributes ->> 'line' as line,
       e.attributes ->> 'delivery_type' as delivery_type, e.attributes ->> 'shot' as shot,
       e.attributes ->> 'phase' as phase,
       e.x as pitch_line, e.y as pitch_length, e.end_x as wagon_x, e.end_y as wagon_y
from match_events e
where e.event_type = 'delivery';

-- Batter vs bowler. Wides do not count as balls faced.
create view v_cricket_matchups as
select batter_id, bowler_id,
       count(*) filter (where coalesce(extra_type, '') <> 'wide') as balls,
       sum(runs_bat) as runs,
       count(*) filter (where wicket) as dismissals,
       count(*) filter (where runs_bat = 0 and coalesce(extra_type, '') <> 'wide') as dots,
       count(*) filter (where runs_bat >= 4) as boundaries,
       round(100.0 * sum(runs_bat) / nullif(count(*) filter (where coalesce(extra_type, '') <> 'wide'), 0), 1) as strike_rate
from v_cricket_deliveries
group by batter_id, bowler_id;

-- ---------------------------------------------------------------------------
-- Baseball
-- ---------------------------------------------------------------------------

create view v_pitch_mix as
select e.player_id as pitcher_id, e.attributes ->> 'pitch_type' as pitch_type,
       count(*) as pitches,
       round(avg((e.attributes ->> 'velocity_mph')::numeric), 1) as avg_velocity_mph,
       round(avg((e.attributes ->> 'spin_rpm')::numeric)) as avg_spin_rpm,
       round(count(*) filter (where e.outcome = 'swinging_strike')::numeric
             / nullif(count(*) filter (where e.outcome in ('swinging_strike', 'foul', 'in_play')), 0), 3) as whiff_rate,
       round(count(*) filter (where e.outcome in ('called_strike', 'swinging_strike', 'foul', 'in_play'))::numeric / count(*), 3) as strike_rate
from match_events e
where e.event_type = 'pitch'
group by e.player_id, e.attributes ->> 'pitch_type';

-- ---------------------------------------------------------------------------
-- American football
-- ---------------------------------------------------------------------------

-- Success: at least 40% of yards to go on 1st down, 60% on 2nd, 100% on 3rd/4th.
create view v_play_efficiency as
select e.team_id, e.event_type as play_type,
       e.attributes ->> 'offensive_formation' as formation, e.attributes ->> 'coverage' as coverage,
       count(*) as plays, round(avg(e.value), 2) as yards_per_play,
       round(avg(case when (e.attributes ->> 'success')::boolean then 1 else 0 end), 3) as success_rate
from match_events e
where e.event_type in ('pass', 'rush') and exists (select 1 from players p where p.id = e.player_id and p.sport_id = 'american_football')
group by e.team_id, e.event_type, e.attributes ->> 'offensive_formation', e.attributes ->> 'coverage';

commit;
