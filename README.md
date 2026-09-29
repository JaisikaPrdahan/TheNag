# TheNag

> **Alerts give you more listings. TheNag gives you fewer, better ones—because it remembers.**

TheNag is a memory-driven opportunity assistant for working professionals and job seekers. It turns a pasted caption or uploaded Reel/video into a structured job opportunity, recalls relevant private preferences, detects duplicates and changed details, weighs source reliability, and recommends a **draft-only** next step. It never applies for a role automatically.

## What the demo shows

- English, Hindi, and Hindi-English caption handling
- File upload or caption paste input
- Jobs & Gigs, Interviews & Hiring Drives, and Uncertain classification
- Private per-user memory, explainable personalized ranking, and decision learning
- Shared source-trust evidence, duplicate detection, deadline/change history
- A functional “Why this?” panel on every card
- Weekly Reflect insights from three weeks of seeded behavior
- PII minimisation: emails and phone numbers are redacted before memory retention
- 28 realistic fictional opportunity records, including duplicates, changed listings, and an unreliable source

## Architecture

```text
Caption / uploaded video
        │
        ├── Whisper transcription (when enabled)
        ├── Groq extraction (when configured)
        └── deterministic demo extraction (fallback)
        │
        ▼
Opportunity pipeline ──► PostgreSQL
  classify · extract · duplicate       reels · opportunities · actions
  source confidence · rank             shared sources · audit events
        │
        ├──► Hindsight private memory bank
        │      preferences · saves · skips · rejections
        │      PII defense runs before retention
        │
        ▼
React dashboard
  ranked cards · Why panel · source trust · Weekly Reflect
```

PostgreSQL stores application records and the shared source-trust bank. Hindsight stores private, per-user memories only. Personal memory is never included in a B2B feed.

For a full step-by-step Windows walkthrough — system installs, every env key
(including Google Calendar and Notion setup), venvs, tests, and a smoke test
checklist — see [docs/SETUP.md](docs/SETUP.md).

## Quick start — demo mode

Requirements: Python 3.11+ and Node.js 20+.

```powershell
cd backend/api
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. With no AI or memory credentials configured, the app uses deterministic demo extraction and seeded private memory.

## Tests and build

```powershell
cd backend/api
pytest tests -v

cd ..\classification
pytest tests -v

cd ..\..\frontend
npm run lint
npm run build
```

## PostgreSQL setup and seed data

```powershell
cd backend
Copy-Item .env.example .env
docker compose up -d
```

Docker applies `db/migrations/*.sql` on a fresh volume. The UI/API demo records are deliberately fictional and live in `backend/demo/seed.json`; no additional seed command is needed. To reapply database migrations during development, use a fresh local volume:

```powershell
docker compose down -v
docker compose up -d
```

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL mode | Application data and shared source-trust bank |
| `GROQ_API_KEY` | Optional | Enables Groq extraction |
| `GROQ_MODEL` | Optional | Defaults to `openai/gpt-oss-120b`; `qwen3-32b` is also supported by configuration |
| `GROQ_API_URL` | Optional | OpenAI-compatible Groq endpoint override |
| `HINDSIGHT_API_URL` | Optional | Hindsight Cloud endpoint |
| `HINDSIGHT_API_KEY` | Optional | Hindsight Cloud credential |
| `HINDSIGHT_BANK_PREFIX` | Optional | Per-user Hindsight bank prefix |
| `ENABLE_LOCAL_WHISPER` | Optional | Set `true` to transcribe uploaded videos through the existing Whisper adapter |
| `CORS_ORIGINS` | Optional | Comma-separated frontend origins |
| `GOOGLE_CLIENT_ID` | Optional | Enables real Google Calendar events on accept |
| `GOOGLE_CLIENT_SECRET` | Optional | Paired with `GOOGLE_CLIENT_ID` |
| `GOOGLE_REFRESH_TOKEN` | Optional | Long-lived refresh token; get one via the [OAuth 2.0 Playground](https://developers.google.com/oauthplayground) using your own client ID/secret (gear icon → "Use your own OAuth credentials") and the `https://www.googleapis.com/auth/calendar` scope |
| `NOTION_API_KEY` | Optional | Enables real Notion notes/pages on accept |
| `NOTION_DATABASE_ID` | Optional | Target Notion database, shared with the integration that owns `NOTION_API_KEY` |

## Integration status

| Capability | Demo mode | Configured mode |
| --- | --- | --- |
| Opportunity extraction | Deterministic heuristic parser | Groq adapter with `gpt-oss-120b` by default |
| Video transcription | Clearly labelled caption/demo fallback | Existing Whisper adapter when `ENABLE_LOCAL_WHISPER=true` |
| User memory | Seeded in-process provider | Hindsight Cloud adapter |
| Application data | Seeded in-process records | PostgreSQL schema and migration included |
| Link ingestion | `POST /api/process-link` runs the real extraction → classification pipeline; needs Tesseract/FFmpeg and `backend/api/requirements.txt`'s extraction deps installed | Same code path; no separate configured mode |
| Accept actions | In-memory mock calendar event + note | Google Calendar event + Notion page when both provider credentials above are set |

The provider boundaries are implemented and demo fallback is tested. Live Groq, Hindsight Cloud, and Whisper credentials were not supplied here, so those hosted paths are not claimed as live-verified.

## Privacy and safety

The Memory Defense layer replaces email addresses and Indian-format phone numbers before a memory record is retained. API responses expose only redaction event types, never the original value. TheNag can create a review draft, checklist, or reminder recommendation, but it never submits an application.

## Business model

TheNag is free for individual job seekers. Revenue comes from verified-opportunity feeds and B2B partnerships with job boards, staffing firms, recruiting platforms, and upskilling platforms. Personal histories, decisions, and private memories are never sold or exposed through those feeds.

## Current limitations and roadmap

- Demo-mode persistence resets when the API process restarts; production PostgreSQL persistence is represented by the migration and API boundary.
- Hosted Hindsight and Groq calls need valid environment credentials before use.
- Instagram share-sheet integration is a roadmap item; direct Reel-link ingestion (`POST /api/process-link`) is implemented, alongside upload and caption paste.
- Scholarships, exams, the remaining nine languages, and full official-source verification are roadmap items.
- The supplied source scores are fictional demonstration data, not real-world reliability claims.

## Content kit

Reusable article, LinkedIn, and team-video templates are in [docs/content/team-content-kit.md](docs/content/team-content-kit.md).
