-- Stage 5: daily club operations: calendar and attendance, tasks, staff, academy and
-- facilities. Contracts (0005) and availability (0006) are already in place.

begin;

create table staff_profiles (
  user_id         uuid not null references app_users (id) on delete cascade,
  organisation_id uuid not null references organisations (id) on delete cascade,
  job_title       text not null,
  department      text not null check (department in ('coaching', 'analysis', 'recruitment', 'performance', 'medical', 'academy', 'operations', 'commercial', 'finance', 'executive')),
  annual_salary   numeric(14, 2),
  currency        char(3),
  started_on      date,
  primary key (user_id, organisation_id)
);

create table calendar_events (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  team_id         uuid references teams (id),
  title           text not null,
  kind            text not null check (kind in ('match', 'training', 'meeting', 'travel', 'media', 'medical', 'academy', 'other')),
  starts_at       timestamptz not null,
  ends_at         timestamptz not null,
  location        text,
  match_id        uuid references matches (id),
  training_session_id uuid references training_sessions (id),
  check (ends_at > starts_at)
);

create index calendar_events_org_idx on calendar_events (organisation_id, starts_at);

-- Attendance for players or staff.
create table attendance (
  event_id   uuid not null references calendar_events (id) on delete cascade,
  player_id  uuid references players (id),
  user_id    uuid references app_users (id),
  status     text not null check (status in ('present', 'late', 'excused', 'absent')),
  recorded_at timestamptz not null default now(),
  check ((player_id is null) <> (user_id is null))
);

create unique index attendance_player_idx on attendance (event_id, player_id) where player_id is not null;
create unique index attendance_user_idx on attendance (event_id, user_id) where user_id is not null;

create table tasks (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  title           text not null,
  description     text,
  assignee_id     uuid references app_users (id),
  player_id       uuid references players (id),
  due_on          date,
  status          text not null default 'todo' check (status in ('todo', 'in_progress', 'done', 'cancelled')),
  priority        text not null default 'normal' check (priority in ('low', 'normal', 'high')),
  created_by      uuid references app_users (id),
  created_at      timestamptz not null default now()
);

create table announcements (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  title           text not null,
  body            text not null,
  audience        text not null check (audience in ('all_staff', 'players', 'coaching', 'academy', 'medical')),
  published_at    timestamptz not null default now(),
  author_id       uuid references app_users (id)
);

-- Academy: guardians and registrations for youth players.
create table guardians (
  id        uuid primary key default gen_random_uuid(),
  full_name text not null,
  email     text,
  phone     text
);

create table academy_registrations (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  player_id       uuid not null references players (id),
  guardian_id     uuid references guardians (id),
  team_id         uuid references teams (id),  -- age-group team
  season_label    text not null,
  status          text not null default 'pending' check (status in ('pending', 'active', 'withdrawn', 'graduated')),
  registered_on   date not null default current_date,
  consent_media   boolean not null default false,
  consent_medical boolean not null default false,
  unique (organisation_id, player_id, season_label)
);

create table facilities (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  kind            text not null check (kind in ('stadium', 'pitch', 'court', 'rink', 'field', 'nets', 'gym', 'pool', 'meeting_room', 'medical_room', 'other')),
  capacity        integer
);

create table facility_bookings (
  id          uuid primary key default gen_random_uuid(),
  facility_id uuid not null references facilities (id) on delete cascade,
  starts_at   timestamptz not null,
  ends_at     timestamptz not null,
  purpose     text not null,
  booked_by   uuid references app_users (id),
  external_party text,  -- set for hires that generate revenue
  check (ends_at > starts_at)
);

-- Prevent double-booking a facility.
create extension if not exists btree_gist;
alter table facility_bookings add constraint facility_bookings_no_overlap
  exclude using gist (facility_id with =, tstzrange(starts_at, ends_at) with &&);

commit;
