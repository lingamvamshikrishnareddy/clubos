-- Row-level security. The API connects as role clubos_app and runs
--   set local app.user_id = '<user uuid>';
-- at the start of each request transaction. Postgres then enforces:
--   * club-private data is visible only to members of that organisation;
--   * medical records only to the organisation's medical staff and admins;
--   * contracts, payroll and finance only to finance, executive, admin and sporting director;
--   * messages only to thread participants.
-- Shared reference data (sports, competitions, matches, players, season stats, market data,
-- model outputs for league players) stays readable by every signed-in user.
-- Table owners and migration/ML jobs (not clubos_app) bypass these policies.

begin;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'clubos_app') then
    create role clubos_app nologin;
  end if;
end $$;

grant usage on schema public to clubos_app;
grant select, insert, update, delete on all tables in schema public to clubos_app;
-- Tables created by later migrations (run by the same owner) get the same grants. New views
-- must also be created with (security_invoker = true) so these policies apply through them.
alter default privileges in schema public grant select, insert, update, delete on tables to clubos_app;

create function app_user_id() returns uuid
language sql stable as $$
  select nullif(current_setting('app.user_id', true), '')::uuid
$$;

create function app_is_member(org uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from memberships m where m.organisation_id = org and m.user_id = app_user_id())
$$;

create function app_has_role(org uuid, roles staff_role[]) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from memberships m
                 where m.organisation_id = org and m.user_id = app_user_id() and m.role = any(roles))
$$;

-- Bypasses RLS on message_participants so thread and message policies don't recurse.
create function app_is_thread_participant(thread uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from message_participants mp where mp.thread_id = thread and mp.user_id = app_user_id())
$$;

-- Organisation that a player belongs to (current squad membership), for player-level data.
create function app_can_see_player_private(player uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from squad_members s
                 where s.player_id = player and s.left_on is null and app_is_member(s.organisation_id))
$$;

-- ---------------------------------------------------------------------------
-- Every table with an organisation_id: members only.
-- ---------------------------------------------------------------------------
do $$
declare t text;
begin
  for t in
    select c.table_name from information_schema.columns c
    join information_schema.tables tb on tb.table_name = c.table_name and tb.table_schema = c.table_schema
    where c.table_schema = 'public' and c.column_name = 'organisation_id' and tb.table_type = 'BASE TABLE'
      and c.table_name not in ('organisations', 'teams')  -- teams are shared reference data
  loop
    execute format('alter table %I enable row level security', t);
    execute format('create policy org_members on %I to clubos_app using (app_is_member(organisation_id)) with check (app_is_member(organisation_id))', t);
  end loop;
end $$;

alter table organisations enable row level security;
create policy org_members on organisations to clubos_app using (app_is_member(id));

-- ---------------------------------------------------------------------------
-- Child tables: visible through their parent.
-- ---------------------------------------------------------------------------
create function app_child_policy(child text, check_sql text) returns void language plpgsql as $$
begin
  execute format('alter table %I enable row level security', child);
  execute format('create policy via_parent on %I to clubos_app using (%s) with check (%s)', child, check_sql, check_sql);
end $$;

do $$ begin
  perform app_child_policy('shortlist_entries', 'exists (select 1 from shortlists p where p.id = shortlist_id and app_is_member(p.organisation_id))');
  perform app_child_policy('video_events', 'exists (select 1 from videos p where p.id = video_id and app_is_member(p.organisation_id))');
  perform app_child_policy('clips', 'exists (select 1 from videos p where p.id = video_id and app_is_member(p.organisation_id))');
  perform app_child_policy('clip_events', 'exists (select 1 from clips c join videos p on p.id = c.video_id where c.id = clip_id and app_is_member(p.organisation_id))');
  perform app_child_policy('playlist_clips', 'exists (select 1 from playlists p where p.id = playlist_id and app_is_member(p.organisation_id))');
  perform app_child_policy('scouting_report_clips', 'exists (select 1 from scouting_reports p where p.id = report_id and app_is_member(p.organisation_id))');
  perform app_child_policy('budget_scenario_moves', 'exists (select 1 from budget_scenarios p where p.id = scenario_id and app_is_member(p.organisation_id))');
  perform app_child_policy('session_loads', 'exists (select 1 from training_sessions p where p.id = session_id and app_is_member(p.organisation_id))');
  perform app_child_policy('attendance', 'exists (select 1 from calendar_events p where p.id = event_id and app_is_member(p.organisation_id))');
  perform app_child_policy('facility_bookings', 'exists (select 1 from facilities p where p.id = facility_id and app_is_member(p.organisation_id))');
  perform app_child_policy('academy_fees', 'exists (select 1 from academy_registrations p where p.id = registration_id and app_is_member(p.organisation_id))');
  perform app_child_policy('academy_renewals', 'exists (select 1 from academy_registrations p where p.id = registration_id and app_is_member(p.organisation_id))');
  perform app_child_policy('payments', 'exists (select 1 from academy_fees f join academy_registrations p on p.id = f.registration_id where f.id = academy_fee_id and app_is_member(p.organisation_id))');
  perform app_child_policy('sponsorship_deals', 'exists (select 1 from sponsors p where p.id = sponsor_id and app_is_member(p.organisation_id))');
  perform app_child_policy('ad_bookings', 'exists (select 1 from ad_inventory p where p.id = inventory_id and app_is_member(p.organisation_id))');
  perform app_child_policy('financial_plan_lines', 'exists (select 1 from financial_plans p where p.id = plan_id and app_has_role(p.organisation_id, ''{finance,executive,admin,sporting_director}''))');
  perform app_child_policy('payslips', 'exists (select 1 from payroll_runs p where p.id = payroll_run_id and app_has_role(p.organisation_id, ''{finance,executive,admin}''))');
  perform app_child_policy('decision_outcomes', 'exists (select 1 from decisions p where p.id = decision_id and app_is_member(p.organisation_id))');
  perform app_child_policy('wellness_checkins', 'app_can_see_player_private(player_id)');
  perform app_child_policy('workload_indicators', 'app_can_see_player_private(player_id)');
  perform app_child_policy('guardians', 'exists (select 1 from academy_registrations r where r.guardian_id = guardians.id and app_is_member(r.organisation_id))');
  -- Medical detail: medical staff and admins of the player's organisation only.
  perform app_child_policy('medical_records',
  'exists (select 1 from availability_status a where a.id = availability_id and app_has_role(a.organisation_id, ''{medical,admin}''))');
  -- Messages: thread participants only.
  perform app_child_policy('message_participants', 'app_is_thread_participant(thread_id)');
  perform app_child_policy('messages', 'app_is_thread_participant(thread_id)');
end $$;

create policy participants_only on message_threads as restrictive to clubos_app
  using (app_is_thread_participant(id) or created_by = app_user_id());

-- ---------------------------------------------------------------------------
-- Stricter rules on sensitive org tables (restrictive: combined with org_members).
-- ---------------------------------------------------------------------------
create policy finance_roles on contracts as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin,sporting_director}'));
create policy finance_roles on payroll_runs as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin}'));
create policy finance_roles on financial_transactions as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin}'));
create policy finance_roles on budgets as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin,sporting_director}'));
create policy finance_roles on financial_forecasts as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin,sporting_director}'));
create policy finance_roles on financial_plans as restrictive to clubos_app
  using (app_has_role(organisation_id, '{finance,executive,admin,sporting_director}'));
-- Staff salaries: finance, executive, admin, or your own row.
create policy finance_or_self on staff_profiles as restrictive to clubos_app
  using (user_id = app_user_id() or app_has_role(organisation_id, '{finance,executive,admin}'));

-- Views run with the querying role's permissions so the policies above still apply.
do $$
declare v text;
begin
  for v in select viewname from pg_views where schemaname = 'public' loop
    execute format('alter view %I set (security_invoker = true)', v);
  end loop;
end $$;

drop function app_child_policy(text, text);

commit;
