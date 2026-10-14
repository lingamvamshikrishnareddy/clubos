-- Provider IDs for competitions, seasons, teams and matches, so re-ingesting a source
-- updates the same rows instead of creating duplicates. Players use player_identities,
-- which also records match confidence (ADR-0002).

begin;

create table source_entity_ids (
  source_id   text not null references data_sources (id),
  entity_type text not null check (entity_type in ('competition', 'season', 'team', 'match')),
  external_id text not null,
  entity_id   uuid not null,
  primary key (source_id, entity_type, external_id)
);

create index source_entity_ids_entity_idx on source_entity_ids (entity_type, entity_id);

commit;
