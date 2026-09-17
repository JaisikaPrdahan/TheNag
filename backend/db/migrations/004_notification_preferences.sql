create table if not exists notification_preferences (
  opportunity_id uuid primary key references opportunities(id) on delete cascade,
  reminders_muted boolean not null default false,
  updated_at timestamptz default now()
);
