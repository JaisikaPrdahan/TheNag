create extension if not exists "pgcrypto";

create table if not exists reels (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  source_type text not null check (source_type in ('share_sheet', 'link', 'upload', 'screenshot')),
  raw_input_ref text, -- the link, or a storage reference to the uploaded file
  caption_text text, -- extracted caption, populated once extraction runs
  hashtags jsonb default '[]', -- array of extracted hashtag strings, populated once extraction runs
  current_stage text not null default 'uploaded' check (current_stage in (
    'uploaded',
    'extracting',
    'extracted',
    'classifying',
    'classified',
    'verifying',
    'verified',
    'generating_action',
    'action_complete',
    'notified',
    'failed'
  )),
  error_message text, -- populated only if current_stage = 'failed'
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
