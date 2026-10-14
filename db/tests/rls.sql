-- Row-level security checks: two clubs, users with different roles. Rolled back.
\set ON_ERROR_STOP on
begin;

insert into organisations (id, name, primary_sport) values
  ('a0000000-0000-0000-0000-000000000001', 'Club A', 'soccer'),
  ('b0000000-0000-0000-0000-000000000001', 'Club B', 'soccer');
insert into app_users (id, email, display_name) values
  ('a0000000-0000-0000-0000-0000000000a1', 'scout-a@example.com', 'Scout A'),
  ('a0000000-0000-0000-0000-0000000000a2', 'doctor-a@example.com', 'Doctor A'),
  ('a0000000-0000-0000-0000-0000000000a3', 'finance-a@example.com', 'Finance A'),
  ('b0000000-0000-0000-0000-0000000000b1', 'scout-b@example.com', 'Scout B');
insert into memberships values
  ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a1', 'scout'),
  ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a2', 'medical'),
  ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a3', 'finance'),
  ('b0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-0000000000b1', 'scout');
insert into players (id, sport_id, full_name) values ('c0000000-0000-0000-0000-000000000001', 'soccer', 'Shared Player');
insert into squad_members (organisation_id, player_id, status) values
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'first_team');
insert into scouting_reports (organisation_id, player_id, author_id, summary, recommendation) values
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a1', 'A report', 'monitor'),
  ('b0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-0000000000b1', 'B report', 'sign');
insert into availability_status (id, player_id, organisation_id, status, starts_on, reason_category) values
  ('d0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'unavailable', current_date, 'injury');
insert into medical_records (availability_id, diagnosis) values ('d0000000-0000-0000-0000-000000000001', 'Test diagnosis');
insert into contracts (organisation_id, player_id, starts_on, ends_on, currency, annual_salary) values
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', '2025-07-01', '2028-06-30', 'GBP', 100000);
insert into message_threads (id, organisation_id, subject, created_by) values
  ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001', 'Private', 'a0000000-0000-0000-0000-0000000000a2');
insert into message_participants (thread_id, user_id) values
  ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a2'),
  ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a3');
insert into messages (thread_id, sender_id, body) values
  ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000a2', 'Hello');

create function pg_temp.expect(label text, actual bigint, expected bigint) returns void language plpgsql as $$
begin
  if actual <> expected then raise exception 'RLS check failed: % (got %, expected %)', label, actual, expected; end if;
end $$;

set local role clubos_app;

-- Scout at club A
set local app.user_id = 'a0000000-0000-0000-0000-0000000000a1';
select pg_temp.expect('scout sees own club reports only', (select count(*) from scouting_reports), 1);
select pg_temp.expect('scout sees availability', (select count(*) from availability_status), 1);
select pg_temp.expect('scout cannot see medical records', (select count(*) from medical_records), 0);
select pg_temp.expect('scout cannot see contracts', (select count(*) from contracts), 0);
select pg_temp.expect('scout cannot read others'' messages', (select count(*) from messages), 0);
select pg_temp.expect('shared players are visible', (select count(*) from players), 1);

-- Doctor at club A
set local app.user_id = 'a0000000-0000-0000-0000-0000000000a2';
select pg_temp.expect('doctor sees medical records', (select count(*) from medical_records), 1);
select pg_temp.expect('doctor reads own thread', (select count(*) from messages), 1);

-- Finance at club A
set local app.user_id = 'a0000000-0000-0000-0000-0000000000a3';
select pg_temp.expect('finance sees contracts', (select count(*) from contracts), 1);
select pg_temp.expect('finance cannot see medical records', (select count(*) from medical_records), 0);
select pg_temp.expect('wage bill view respects policies', (select count(*) from v_wage_bill), 1);

-- Scout at club B
set local app.user_id = 'b0000000-0000-0000-0000-0000000000b1';
select pg_temp.expect('other club sees only its report', (select count(*) from scouting_reports), 1);
select pg_temp.expect('other club cannot see club A availability', (select count(*) from availability_status), 0);
select pg_temp.expect('other club wage bill view is empty', (select count(*) from v_wage_bill), 0);

-- Writes are checked too: club B cannot create a report for club A.
do $$
begin
  insert into scouting_reports (organisation_id, player_id, author_id, summary, recommendation) values
    ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-0000000000b1', 'Sneaky', 'sign');
  raise exception 'expected RLS to reject the insert';
exception when insufficient_privilege then null;
end $$;

-- No user set: nothing club-private is visible.
reset app.user_id;
set local app.user_id = '';
select pg_temp.expect('anonymous sees no reports', (select count(*) from scouting_reports), 0);

rollback;
