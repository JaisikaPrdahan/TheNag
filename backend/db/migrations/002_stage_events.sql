create table if not exists stage_events (
  id uuid primary key default gen_random_uuid(),
  reel_id uuid not null references reels(id) on delete cascade,
  stage text not null,
  status text not null check (status in ('started', 'completed', 'failed')),
  metadata jsonb, -- optional extra detail, e.g. {"language_detected": "hi", "ocr_confidence": 0.6}
  created_at timestamptz default now()
);
