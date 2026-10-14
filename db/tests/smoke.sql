-- Exercises the Stage 1 schema end to end. Runs in a transaction that is rolled back.
\set ON_ERROR_STOP on
begin;

insert into competitions (id, sport_id, name, country, gender, tier)
  values ('00000000-0000-0000-0000-000000000001', 'soccer', 'Test League', 'Testland', 'men', 1);
insert into seasons (id, competition_id, label)
  values ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '2025/26');
insert into teams (id, sport_id, name) values
  ('00000000-0000-0000-0000-000000000003', 'soccer', 'Riverside FC'),
  ('00000000-0000-0000-0000-000000000004', 'soccer', 'Hillcrest United');
insert into matches (id, season_id, home_team_id, away_team_id)
  values ('00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000002',
          '00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000004');
insert into players (id, sport_id, full_name, primary_role)
  values ('00000000-0000-0000-0000-000000000006', 'soccer', 'Test Player', 'full_back');
insert into player_identities (source_id, external_id, player_id, match_method, confidence)
  values ('statsbomb_open_data', '5503', '00000000-0000-0000-0000-000000000006', 'exact', 1);
insert into player_match_appearances (id, player_id, match_id, team_id, role_key, minutes, source_id, source_record_id)
  values ('00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000006',
          '00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000003',
          'full_back', 90, 'statsbomb_open_data', '3788741');
insert into player_metric_values (appearance_id, metric_key, value) values
  ('00000000-0000-0000-0000-000000000007', 'progressive_passes', 6),
  ('00000000-0000-0000-0000-000000000007', 'xa', null);

insert into organisations (id, name, primary_sport)
  values ('00000000-0000-0000-0000-000000000008', 'Demo Club', 'soccer');
insert into app_users (id, email, display_name)
  values ('00000000-0000-0000-0000-000000000009', 'scout@example.com', 'Demo Scout');
insert into memberships values ('00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000009', 'scout');
insert into shortlists (id, organisation_id, name, role_key, created_by)
  values ('00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-000000000008',
          'Left-back targets', 'full_back', '00000000-0000-0000-0000-000000000009');
insert into shortlist_entries (shortlist_id, player_id, added_by)
  values ('00000000-0000-0000-0000-00000000000a', '00000000-0000-0000-0000-000000000006',
          '00000000-0000-0000-0000-000000000009');
insert into scouting_reports (organisation_id, player_id, author_id, role_assessed, rating, summary, recommendation)
  values ('00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000006',
          '00000000-0000-0000-0000-000000000009', 'full_back', 7, 'Strong progressive passer.', 'monitor');

-- Constraint checks: a team cannot play itself.
do $$
begin
  insert into matches (season_id, home_team_id, away_team_id)
    values ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003',
            '00000000-0000-0000-0000-000000000003');
  raise exception 'expected check violation';
exception when check_violation then null;
end $$;

rollback;
