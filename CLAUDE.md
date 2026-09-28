# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

TheNag turns a shared Instagram Reel about an educational/early-career opportunity (Job, Internship, Scholarship, College/Admission, Interview, Exam, Hackathon/Competition, or Uncertain) into a verified deadline, document checklist, and a single calendar event. Every extracted fact carries a green/yellow/red confidence tag — nothing is silently guessed. Product spec: `docs/spec.md`; ownership and interfaces: `docs/team-structure.md`; locked technical decisions with rationale: `docs/engineering-decisions.md`.

## Pipeline architecture

The backend is a staged pipeline. Each stage is owned by a different team member ("Person 1/2/3" in code comments and docs), lives in its own folder, and hands off to the next via an in-memory dict plus the shared Postgres DB:

1. **Extraction** (`backend/extraction/`, Person 1) — `combine.py::run_extraction(path_or_url)` is the single integration point; callers should use it, not the `ocr/` or `audio/` subsystems directly. It downloads URL input (`ocr/url_downloader.py`, yt-dlp / instaloader), runs Tesseract OCR (`ocr/pipeline.py`), and runs Whisper (`audio/transcription.py`, video only). Output shape is **locked** in `backend/extraction/contracts/extraction_output.md`.
2. **Classification** (`backend/classification/`, Person 2) — `classifier.py::classify_extraction(extraction)` returns `models.ClassifiedFacts`. Keyword scoring from `keywords.py` (weights: hashtags 3, caption 2, OCR 2, transcript 1), confidence tiers in `confidence.py`, date parsing in `date_resolver.py`. `db_writes.py::classify_and_persist()` wraps it with DB persistence.
3. **Actions** (`backend/actions/`, Person 3) — verification, calendar event, notes, notifications. Not yet implemented.
4. **API** (`backend/api/`) — orchestration layer exposing the pipeline to the frontend. Not yet implemented.
5. **Frontend** (`frontend/`, Vite + React) — planned, not yet in the repo.

### Contract rules that are easy to get wrong

- `caption_text`, `hashtags`, and `post_date` only exist for URL input; for local files they are `None`/`[]`.
- **Relative dates must resolve against the reel's `post_date`**, not the current time. `classify_extraction()` already does this (`reference_date = parse_post_date(extraction.get("post_date"))`); any other caller of `resolve_dates()` must pass `reference_date` the same way, or it silently falls back to "now" (this was a real bug — regression test in `classification/tests/test_post_date_regression.py`). `parse_post_date()` itself falls back to "now" only when `post_date` is missing or unparseable (local-file input). Relative dates stay tagged yellow even after resolution.
- `ocr_results` never contains red-confidence entries (dropped in the OCR pipeline). Transcripts have no confidence score and may be empty (music) or contain hallucinations — don't treat them as green.
- Whisper model size is locked to `"medium"`; Tesseract (not Cloud Vision) is locked. Check `docs/engineering-decisions.md` before changing any "locked" decision.
- Classifier category labels (`"Hackathon/Competition"`) differ from DB values (`hackathon_competition`); the mapping is `CATEGORY_TO_DB_VALUE` in `classification/db_writes.py`. A new category must be added there and to the check constraint in `backend/db/migrations/003_opportunities.sql`.

### Database

Shared Postgres (`backend/db/`): `client.py::get_connection()` (psycopg2, `RealDictCursor`, reads `DATABASE_URL`) is the only place connections are opened — subsystems import it rather than creating their own. Tables: `reels` (stage tracker via `current_stage`), `stage_events` (append-only log — always INSERT, never UPDATE), `opportunities` (created by classification, only updated by actions), `notification_preferences`. Each stage sets only its own `current_stage` transitions and sets `failed` + `error_message` only for failures in its own stage. Full reference including who writes what: `docs/database-schema.md`.

### Imports / module layout

There are no packages or `__init__.py` files. Modules import siblings by bare name and cross-folder access is done via `sys.path.insert` (e.g. `combine.py` adds `ocr/` and `audio/`; `db_writes.py` adds `backend/` to reach `db.client`; tests add their parent folder). Follow the same pattern and run scripts/tests from inside the relevant subsystem folder.

## Environment setup

Each Python subsystem has its **own** `venv` and `requirements.txt` (`extraction/ocr`, `extraction/audio`, `extraction/` for the combined pipeline which needs both, `classification/`, `actions/`). Don't add one subsystem's dependencies to another's. New dependencies go into that subsystem's `requirements.txt` in the same commit; new subsystem folders must ship with a `README.md` (including its input/output contract) and `requirements.txt`.

```
cd backend/<subsystem>
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

System dependencies for extraction: Tesseract and FFmpeg on PATH (Whisper pulls in PyTorch — large install).

Database (`docker-compose.yml` and `.env.example` live in `backend/`, not the repo root):

```
cd backend
docker compose up -d                          # runs db/migrations/*.sql on first start
docker compose down -v && docker compose up -d  # wipe and re-run migrations after schema changes
```
`DATABASE_URL=postgresql://thenag:thenag_dev@localhost:5432/thenag` — only needed for `db_writes.py`; classification tests mock the connection.

## Commands

```
# Run extraction end-to-end (from backend/extraction, combined venv)
python combine.py path\to\reel.mp4
python combine.py "https://www.instagram.com/reel/SOME_ID/"

# Tests (from the subsystem folder, with its venv active)
cd backend/classification && pytest tests/ -v
pytest tests/test_date_resolver.py -v
pytest tests/test_date_resolver.py::test_explicit_date_from_caption_is_green
cd backend/extraction/ocr && pytest tests/ -v     # the combined backend/extraction/venv
cd backend/extraction/audio && pytest tests/ -v   # runs both OCR and audio suites
```

No linter or formatter is configured.

## Git workflow

Branch off `main` as `your-name/short-description`; `main` is protected and requires a PR approved by the team lead (squash and merge). See `CONTRIBUTING.md`.
