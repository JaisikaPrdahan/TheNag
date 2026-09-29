create table if not exists opportunities (
  id uuid primary key default gen_random_uuid(),
  reel_id uuid not null references reels(id) on delete cascade,
  user_id uuid,
  primary_category text not null check (primary_category in (
    'jobs_gigs', 'interviews_hiring_drives', 'uncertain'
  )),
  secondary_categories jsonb default '[]', -- array of category strings
  extracted_facts jsonb not null default '[]', -- array of {value, confidence, type, source}
  notes jsonb not null default '{}', -- the notes object: checklist, documents, milestones, category-specific detail
  calendar_event_id text, -- null until the calendar event is actually created
  verification_conflicts jsonb, -- null if no conflict; otherwise {reel_date, official_date, source_url}
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
