-- Application data stays in PostgreSQL. Private preference/decision memory is
-- retained in a per-user Hindsight bank and is intentionally not duplicated here.

alter table opportunities drop constraint if exists opportunities_primary_category_check;
alter table opportunities add constraint opportunities_primary_category_check
  check (primary_category in ('jobs_gigs', 'interviews_hiring_drives', 'uncertain'));

alter table opportunities
  add column if not exists role_title text,
  add column if not exists company text,
  add column if not exists location text,
  add column if not exists work_mode text,
  add column if not exists employment_type text,
  add column if not exists required_skills jsonb not null default '[]',
  add column if not exists experience_level text,
  add column if not exists compensation text,
  add column if not exists application_deadline date,
  add column if not exists application_link text,
  add column if not exists source_creator text,
  add column if not exists extraction_confidence integer,
  add column if not exists source_trust_score integer,
  add column if not exists personalized_rank integer,
  add column if not exists duplicate_status text default 'new'
    check (duplicate_status in ('new', 'exact', 'updated', 'similar_source')),
  add column if not exists changed_fields jsonb not null default '[]',
  add column if not exists recommended_action text,
  add column if not exists why_summary jsonb not null default '[]';

create table if not exists opportunity_actions (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  user_id uuid not null,
  action text not null check (action in ('saved', 'accepted', 'rejected', 'skipped', 'viewed')),
  reason text,
  created_at timestamptz default now()
);

create table if not exists sources (
  id uuid primary key default gen_random_uuid(),
  source_key text unique not null,
  display_name text not null,
  observed_count integer not null default 0,
  confirmed_count integer not null default 0,
  misleading_count integer not null default 0,
  changed_count integer not null default 0,
  trust_score integer not null default 50 check (trust_score between 0 and 100),
  evidence jsonb not null default '[]',
  updated_at timestamptz default now()
);

create index if not exists idx_opportunities_user_rank on opportunities(user_id, personalized_rank desc);
create index if not exists idx_actions_user_created on opportunity_actions(user_id, created_at desc);
