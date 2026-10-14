-- Match results that the score alone cannot express: cricket super-over and DLS winners,
-- ties and no-results. Standings use the recorded result when there is one.

begin;

alter table matches
  add column winner_team_id uuid references teams (id),
  add column result text check (result in ('win', 'draw', 'tie', 'no_result'));

drop view v_league_table;

-- Standings for the regular season, ranked by the competition's standings rule:
-- points (football, cricket) or win percentage (NFL, NBA). A recorded winner overrides the
-- score comparison (super overs, DLS); no-results earn the rule's noResult points.
create view v_league_table with (security_invoker = true) as
with results as (
  select m.season_id, se.competition_id, t.team_id,
         case when m.winner_team_id is not null then (m.winner_team_id = t.team_id)::int
              when m.result = 'no_result' then 0
              when (t.home and m.home_score > m.away_score) or (not t.home and m.away_score > m.home_score) then 1 else 0 end as win,
         case when m.winner_team_id is null and coalesce(m.result, '') <> 'no_result' and m.home_score = m.away_score
              then 1 else 0 end as draw,
         case when m.winner_team_id is not null then (m.winner_team_id <> t.team_id)::int
              when m.result = 'no_result' then 0
              when (t.home and m.home_score < m.away_score) or (not t.home and m.away_score < m.home_score) then 1 else 0 end as loss,
         case when m.result = 'no_result' then 1 else 0 end as no_result,
         case when t.home then m.home_score else m.away_score end as scored,
         case when t.home then m.away_score else m.home_score end as conceded
  from matches m
  join seasons se on se.id = m.season_id
  cross join lateral (values (m.home_team_id, true), (m.away_team_id, false)) as t(team_id, home)
  where m.stage = 'regular'
    and ((m.home_score is not null and m.away_score is not null) or m.result = 'no_result' or m.winner_team_id is not null)
), totals as (
  select r.season_id, r.competition_id, r.team_id, count(*) as played, sum(win) as won, sum(draw) as drawn,
         sum(loss) as lost, sum(no_result) as no_results, sum(scored) as scored, sum(conceded) as conceded
  from results r
  group by r.season_id, r.competition_id, r.team_id
), scored_totals as (
  select t.*, c.name as competition, c.rules,
         t.won * coalesce((c.rules -> 'standings' ->> 'win')::int, 3)
           + t.drawn * coalesce((c.rules -> 'standings' ->> 'draw')::int, 1)
           + t.lost * coalesce((c.rules -> 'standings' ->> 'loss')::int, 0)
           + t.no_results * coalesce((c.rules -> 'standings' ->> 'noResult')::int, 0) as points,
         round((t.won + 0.5 * t.drawn) / nullif(t.played - t.no_results, 0), 3) as win_percentage
  from totals t
  join competitions c on c.id = t.competition_id
)
select s.season_id, se.label as season_label, s.competition_id, s.competition, s.team_id, tm.name as team,
       grp.name as group_name,
       s.played, s.won, s.drawn, s.lost, s.no_results, s.scored, s.conceded, s.scored - s.conceded as difference,
       s.points, s.win_percentage,
       -- Tie-breaks other than score difference (e.g. cricket net run rate) are not modelled yet.
       rank() over (partition by s.season_id order by s.sort_key desc nulls last,
                    s.scored - s.conceded desc nulls last, s.scored desc nulls last) as position,
       -- Position within the team's division (NFL, NBA) or tournament group (e.g. World Cup).
       rank() over (partition by s.season_id, grp.name order by s.sort_key desc nulls last,
                    s.scored - s.conceded desc nulls last, s.scored desc nulls last) as group_position
from (
  select st.*, case when st.rules -> 'standings' ->> 'method' = 'win_percentage' then st.win_percentage
                    else st.points end as sort_key
  from scored_totals st
) s
join seasons se on se.id = s.season_id
join teams tm on tm.id = s.team_id
left join lateral (
  select g.name from competition_group_teams gt
  join competition_groups g on g.id = gt.group_id
  where g.competition_id = s.competition_id and gt.team_id = s.team_id
    and (g.kind = 'division' or (g.kind = 'group' and gt.from_season = se.label))
  order by g.kind
  limit 1
) grp on true;

commit;
