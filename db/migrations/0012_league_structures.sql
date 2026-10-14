-- Real league structures and rules: conferences and divisions, league pyramids with
-- promotion and relegation, match stages, and standings computed by each league's rules.
-- Reference data comes from packages/leagues/leagues.json (clubos-leagues load).

begin;

alter table competitions
  add column reference_key text unique,  -- e.g. 'nfl', 'ipl', 'efl_championship'
  add column pyramid text,                -- e.g. 'english_football'; tier gives the level
  -- League rules for the season named inside, e.g. salary cap, auction purse, squad size,
  -- overseas-player limits, standings method, promotion and relegation.
  add column rules jsonb not null default '{}';

insert into data_sources (id, name, licence, attribution, url) values
  ('clubos_reference', 'ClubOS league reference data', 'Factual reference data maintained in the repository', null, null),
  ('nflverse', 'nflverse data', 'CC BY 4.0', 'Data from nflverse (nflverse.com)', 'https://github.com/nflverse/nflverse-data'),
  ('cricsheet', 'Cricsheet', 'Open Data Commons Attribution License (check current terms)', 'Data from Cricsheet (cricsheet.org)', 'https://cricsheet.org');

create table competition_groups (
  id             uuid primary key default gen_random_uuid(),
  competition_id uuid not null references competitions (id) on delete cascade,
  parent_id      uuid references competition_groups (id) on delete cascade,
  kind           text not null check (kind in ('conference', 'division', 'group', 'league')),
  name           text not null,
  unique (competition_id, name)
);

create table competition_group_teams (
  group_id    uuid not null references competition_groups (id) on delete cascade,
  team_id     uuid not null references teams (id) on delete cascade,
  from_season text,
  to_season   text,
  primary key (group_id, team_id)
);

alter table teams add column short_name text;

alter table matches
  add column stage text not null default 'regular'
    check (stage in ('regular', 'play_in', 'playoff', 'qualifier', 'eliminator', 'final', 'friendly')),
  add column round text;

-- Standings for the regular season, ranked by the competition's standings rule:
-- points (football, cricket) or win percentage (NFL, NBA).
create view v_league_table with (security_invoker = true) as
with results as (
  select m.season_id, se.competition_id, t.team_id,
         case when (t.home and m.home_score > m.away_score) or (not t.home and m.away_score > m.home_score) then 1 else 0 end as win,
         case when m.home_score = m.away_score then 1 else 0 end as draw,
         case when (t.home and m.home_score < m.away_score) or (not t.home and m.away_score < m.home_score) then 1 else 0 end as loss,
         case when t.home then m.home_score else m.away_score end as scored,
         case when t.home then m.away_score else m.home_score end as conceded
  from matches m
  join seasons se on se.id = m.season_id
  cross join lateral (values (m.home_team_id, true), (m.away_team_id, false)) as t(team_id, home)
  where m.stage = 'regular' and m.home_score is not null and m.away_score is not null
), totals as (
  select r.season_id, r.competition_id, r.team_id, count(*) as played, sum(win) as won, sum(draw) as drawn,
         sum(loss) as lost, sum(scored) as scored, sum(conceded) as conceded
  from results r
  group by r.season_id, r.competition_id, r.team_id
)
select t.season_id, se.label as season_label, c.id as competition_id, c.name as competition, t.team_id, tm.name as team,
       t.played, t.won, t.drawn, t.lost, t.scored, t.conceded, t.scored - t.conceded as difference,
       t.won * coalesce((c.rules -> 'standings' ->> 'win')::int, 3)
         + t.drawn * coalesce((c.rules -> 'standings' ->> 'draw')::int, 1)
         + t.lost * coalesce((c.rules -> 'standings' ->> 'loss')::int, 0) as points,
       round((t.won + 0.5 * t.drawn) / nullif(t.played, 0), 3) as win_percentage,
       rank() over (
         partition by t.season_id
         order by case when c.rules -> 'standings' ->> 'method' = 'win_percentage'
                       then (t.won + 0.5 * t.drawn) / nullif(t.played, 0)
                       else t.won * coalesce((c.rules -> 'standings' ->> 'win')::int, 3)
                            + t.drawn * coalesce((c.rules -> 'standings' ->> 'draw')::int, 1) end desc,
                  t.scored - t.conceded desc, t.scored desc
       ) as position
from totals t
join competitions c on c.id = t.competition_id
join seasons se on se.id = t.season_id
join teams tm on tm.id = t.team_id;

commit;
