# TheNag — Database Schema (Postgres in Docker)

Self-hosted Postgres, run via Docker, is the single database for both pipeline stage tracking and the actual opportunity data. This doc defines the tables, matching the pipeline stages and data contracts already locked in `docs/spec.md` and `docs/team-structure.md`.

---

## Who uses which table (read this first)

If you're not sure which part of this doc matters to you, start here.

- **Person 1 (Extraction):** You mainly write to `reels`. When a reel comes in, you set `current_stage` to `extracting`, do your OCR/Whisper/caption work, fill in `caption_text` and `hashtags`, then set `current_stage` to `extracted`. You also insert rows into `stage_events` each time you start or finish, so there's a record of what you did. You do not touch `opportunities` or `notification_preferences` at all.
- **Person 2 (Classification):** You read `reels` (specifically `caption_text` and `hashtags`, plus whatever Person 1 hands off outside the database, like OCR/transcript text). You write to `reels.current_stage` (`classifying` → `classified`) and to `stage_events`. You are the one who first creates the row in `opportunities` — that's where `primary_category`, `secondary_categories`, and `extracted_facts` (with their confidence levels) get set.
- **Person 3 (Actions):** You read the `opportunities` row Person 2 created, and update it — adding `notes`, `calendar_event_id`, and `verification_conflicts` once you've done the official-source check and built the calendar event. You also update `reels.current_stage` through `verifying` → `verified` → `generating_action` → `action_complete` → `notified`, write to `stage_events` throughout, and you own `notification_preferences` entirely (creating the row and updating `reminders_muted` when the user toggles it).
- **Person 4 (Frontend):** You mostly *read* — `reels.current_stage` to show progress, `opportunities` to display the notes/facts/checklist, `notification_preferences` to show and update the mute toggle. You don't write directly to the database at all; you call the backend API (owned by Person 3), and the API does the actual database writes.

If two of you are ever confused about who's supposed to update a field, check this section first — it should cover it.

---

## Docker setup

`docker-compose.yml` lives in `backend/`:

```yaml
services:
  db:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_USER: thenag
      POSTGRES_PASSWORD: thenag_dev
      POSTGRES_DB: thenag
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/migrations:/docker-entrypoint-initdb.d

volumes:
  pgdata:
```

The `./db/migrations:/docker-entrypoint-initdb.d` line (relative to `backend/`) means any `.sql` file in `backend/db/migrations/` runs automatically the first time the container starts — that's where the table definitions below go.

Run all of the commands below from `backend/`.

**To start the database:**
```
docker compose up -d
```

**To stop it:**
```
docker compose down
```

**To wipe it and start fresh** (useful if you change the schema during early development):
```
docker compose down -v
docker compose up -d
```

The `-v` flag also removes the `pgdata` volume, so all data is deleted — only do this in local dev, never against real data.

Each teammate needs Docker Desktop installed and running locally. The database connection string for local dev will be:
```
postgresql://thenag:thenag_dev@localhost:5432/thenag
```
This goes in `backend/.env` as `DATABASE_URL` (copy it from `backend/.env.example`) — already gitignored.

---

## Table 1: `reels`

**Owned by:** Person 1 creates and mostly updates this table. Person 2 and Person 3 also update `current_stage` as the reel moves through their stages. Person 4 only reads it.

One row per shared reel. This is the stage tracker — it exists from the moment a reel is shared until the pipeline finishes or fails.

```sql
create extension if not exists "pgcrypto";

create table reels (
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
```

**Note on `caption_text` and `hashtags`:** these live on `reels` rather than `opportunities` since they're properties of the reel itself, extracted early in the pipeline (Person 1's stage), before classification or verification has happened — and per Section 2/3 of the spec, hashtags are a classification signal Person 2 reads directly from here, not something derived later.

**Who writes to this, step by step:** Person 1 (Extraction) updates `current_stage` from `uploaded` → `extracting` → `extracted`, and fills in `caption_text` and `hashtags` along the way. Person 2 (Classification) updates `extracted` → `classifying` → `classified`. Person 3 (Actions) updates `classified` → `verifying` → `verified` → `generating_action` → `action_complete` → `notified`. Any of the three backend people can set `current_stage` to `failed` with an `error_message` if something breaks in their own stage — you're only ever responsible for setting `failed` during your own stage, not diagnosing someone else's.

---

## Table 2: `stage_events`

**Owned by:** all three backend people (Person 1, 2, 3) write to this — nobody "owns" it exclusively, it's a shared log. Person 4 can read it if useful for debugging the frontend, but won't normally need to.

An append-only log of every stage transition, for debugging and for anyone asking "what exactly happened to this reel." `reels.current_stage` tells you where a reel is *right now*, `stage_events` tells you its full history.

```sql
create table stage_events (
  id uuid primary key default gen_random_uuid(),
  reel_id uuid not null references reels(id) on delete cascade,
  stage text not null,
  status text not null check (status in ('started', 'completed', 'failed')),
  metadata jsonb, -- optional extra detail, e.g. {"language_detected": "hi", "ocr_confidence": 0.6}
  created_at timestamptz default now()
);
```

Every subsystem writes one row here every time it starts or finishes its part of the pipeline for a given reel — this table is never updated, only inserted into. **Practical rule for beginners:** if you're not sure whether to `INSERT` or `UPDATE` a row, in this table it's always `INSERT` — you're adding a new line to a log, never editing an old one.

---

## Table 3: `opportunities`

**Owned by:** Person 2 creates the row (setting `primary_category`, `secondary_categories`, `extracted_facts`). Person 3 then updates that same row (setting `notes`, `calendar_event_id`, `verification_conflicts`) — Person 3 never creates a new row here, only updates the one Person 2 already made. Person 4 only reads it, to display everything to the user.

The actual extracted, classified, verified opportunity — one row per opportunity, linked back to the reel it came from. This matches the Person 3 → Person 4 interface object from `docs/team-structure.md`.

```sql
create table opportunities (
  id uuid primary key default gen_random_uuid(),
  reel_id uuid not null references reels(id) on delete cascade,
  user_id uuid,
  primary_category text not null check (primary_category in (
    'job', 'internship', 'scholarship', 'college_admission',
    'interview', 'exam', 'hackathon_competition', 'uncertain'
  )),
  secondary_categories jsonb default '[]', -- array of category strings
  extracted_facts jsonb not null default '[]', -- array of {value, confidence, type, source}
  notes jsonb not null default '{}', -- the notes object: checklist, documents, milestones, category-specific detail
  calendar_event_id text, -- null until the calendar event is actually created
  verification_conflicts jsonb, -- null if no conflict; otherwise {reel_date, official_date, source_url}
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

**Note on `extracted_facts` shape:** each element should look like:
```json
{ "value": "Nov 15", "confidence": "yellow", "type": "application_closing", "source": "ocr:0:12" }
```

**Note on `notes` shape:** this is intentionally a flexible JSON object rather than a rigid table, since its contents genuinely differ by category (a hackathon's notes has `location`/`team_size`/`domain`, an exam's has `required_documents`) — matching the spec's Section 3.1 design.

---

## Table 4: `notification_preferences`

**Owned by:** Person 3 creates this row (right after the opportunity is created, defaulting `reminders_muted` to `false`). Person 4 reads it to show the mute toggle in the UI, and calls Person 3's API to flip it — Person 4 never writes to the database directly, same as everywhere else in this doc.

Per-opportunity mute state, matching Section 6.1 of the spec (per-opportunity toggle, separate from global settings).

```sql
create table notification_preferences (
  opportunity_id uuid primary key references opportunities(id) on delete cascade,
  reminders_muted boolean not null default false,
  updated_at timestamptz default now()
);
```

---

## Where this lives in the codebase

```
backend/
  db/
    client.py          (shared Postgres connection, used by all three subsystems)
    migrations/
      001_reels.sql
      002_stage_events.sql
      003_opportunities.sql
      004_notification_preferences.sql
    README.md
  docker-compose.yml
  .env.example
```

Since all three backend subsystems read/write to the same database, put the shared connection setup in `backend/db/client.py` rather than duplicating it in `extraction/`, `classification/`, and `actions/` separately. A basic version using `psycopg2` or `SQLAlchemy`:

```python
# backend/db/client.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
```

Each subsystem imports this rather than opening its own connection independently.

---

## Live progress without polling

Plain Postgres doesn't have Supabase's built-in realtime push feature. Two options if you want the frontend to show live pipeline progress rather than polling:

1. **Simplest for a 2-week build: short-interval polling.** The frontend calls a `GET /reels/:id/status` endpoint (owned by Person 3's API layer) every couple of seconds while a reel is processing, and stops once `current_stage` is `action_complete`, `notified`, or `failed`. Not elegant, but reliable and fast to build.
2. **More real-time, more setup: Postgres `LISTEN`/`NOTIFY` plus WebSockets.** The backend sends a `NOTIFY` whenever `reels.current_stage` changes, a small listener process picks it up and pushes it over a WebSocket to the frontend. This is the "correct" way to do it, but it's real additional infrastructure — worth doing only if polling genuinely feels too slow once the app is working.

Given the 2-week timeline, I'd start with polling and only move to `LISTEN`/`NOTIFY` if it becomes a real problem.