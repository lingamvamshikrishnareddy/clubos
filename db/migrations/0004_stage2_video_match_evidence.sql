-- Stage 2: video, tagged events, clips and tactical reports.
-- Video files live in object storage; only their location and metadata are stored here.

begin;

create table videos (
  id               uuid primary key default gen_random_uuid(),
  organisation_id  uuid not null references organisations (id) on delete cascade,
  match_id         uuid references matches (id),
  title            text not null,
  storage_uri      text not null,  -- e.g. s3://bucket/key
  duration_seconds numeric(8, 1) check (duration_seconds > 0),
  angle            text check (angle in ('broadcast', 'tactical', 'end_zone', 'behind_goal', 'other')),
  -- Offset of match clock zero within the file, so events can be linked by match time.
  kickoff_offset_seconds numeric(8, 1) not null default 0,
  uploaded_by      uuid references app_users (id),
  uploaded_at      timestamptz not null default now()
);

create index videos_match_idx on videos (organisation_id, match_id);

-- A tagged moment. event_type is a key from the sport module's eventTypes; tags hold
-- values from its videoTags vocabulary, e.g. {"coverage": "cover 3", "personnel": "11"}.
create table video_events (
  id            uuid primary key default gen_random_uuid(),
  video_id      uuid not null references videos (id) on delete cascade,
  start_seconds numeric(8, 1) not null check (start_seconds >= 0),
  end_seconds   numeric(8, 1) not null,
  event_type    text not null,
  player_id     uuid references players (id),
  team_id       uuid references teams (id),
  -- Position on a normalised 0–100 x 0–100 playing surface, when relevant.
  x             numeric(5, 2) check (x between 0 and 100),
  y             numeric(5, 2) check (y between 0 and 100),
  outcome       text,
  tags          jsonb not null default '{}',
  tagged_by     uuid references app_users (id),
  -- 'manual' today; 'model' once automatic tagging exists, so staff can tell them apart.
  tag_method    text not null default 'manual' check (tag_method in ('manual', 'model', 'imported')),
  created_at    timestamptz not null default now(),
  check (end_seconds >= start_seconds)
);

create index video_events_video_idx on video_events (video_id, start_seconds);
create index video_events_player_idx on video_events (player_id);
create index video_events_tags_idx on video_events using gin (tags);

create table clips (
  id            uuid primary key default gen_random_uuid(),
  video_id      uuid not null references videos (id) on delete cascade,
  title         text not null,
  start_seconds numeric(8, 1) not null check (start_seconds >= 0),
  end_seconds   numeric(8, 1) not null,
  notes         text,
  created_by    uuid references app_users (id),
  created_at    timestamptz not null default now(),
  check (end_seconds > start_seconds)
);

create table clip_events (
  clip_id  uuid not null references clips (id) on delete cascade,
  event_id uuid not null references video_events (id) on delete cascade,
  primary key (clip_id, event_id)
);

create table playlists (
  id              uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references organisations (id) on delete cascade,
  name            text not null,
  purpose         text check (purpose in ('opponent_analysis', 'player_feedback', 'recruitment', 'coaching', 'other')),
  created_by      uuid references app_users (id),
  created_at      timestamptz not null default now()
);

create table playlist_clips (
  playlist_id uuid not null references playlists (id) on delete cascade,
  clip_id     uuid not null references clips (id) on delete cascade,
  position    integer not null,
  primary key (playlist_id, clip_id)
);

-- Clips can serve as evidence in scouting reports.
create table scouting_report_clips (
  report_id uuid not null references scouting_reports (id) on delete cascade,
  clip_id   uuid not null references clips (id) on delete cascade,
  primary key (report_id, clip_id)
);

create table tactical_reports (
  id               uuid primary key default gen_random_uuid(),
  organisation_id  uuid not null references organisations (id) on delete cascade,
  match_id         uuid references matches (id),
  opponent_team_id uuid references teams (id),
  kind             text not null check (kind in ('pre_match', 'post_match', 'opponent_trend', 'own_trend')),
  title            text not null,
  summary          text not null,
  -- Structured findings: [{"finding": "...", "evidence_clip_ids": [...], "metric": {...}}]
  findings         jsonb not null default '[]',
  author_id        uuid references app_users (id),
  created_at       timestamptz not null default now()
);

commit;
