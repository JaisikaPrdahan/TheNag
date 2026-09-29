# Handoff — what's left

## CURRENT STATE

- The link pipeline is implemented: Reel URL → extraction → classification →
  private memory/source trust → ranking and Why panel → Accept action. Caption
  and upload remain reliable fallback inputs.
- The API uses mock/deterministic providers without credentials. Groq hosted
  transcription, Hindsight Cloud, Google Calendar, and Notion are therefore
  still mocked in this checkout.
- Current test results: API **16/16**, classification **34/34**, OCR **16/16**
  (includes the cache-hit and caption/OCR-on-timeout paths), audio **5/5**
  (includes the hard timeout worker-termination path).
- Local CPU transcription now uses Whisper `small` in a separate process with
  a 60-second hard timeout. Groq hosted transcription is used when
  `GROQ_API_KEY` is available.

## KNOWN ISSUES

- The requested target Reel cache is not populated yet. One real retrieval
  attempt was made on 2026-09-29; it stopped because FFmpeg is not on this
  machine's PATH. Do not retry in a loop. Install FFmpeg, then make one real
  run to create `backend/demo/cached_reels/<hash>.json`.
- `backend/.env` has blank values for `GROQ_API_KEY`, `HINDSIGHT_API_URL`,
  `HINDSIGHT_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `GOOGLE_REFRESH_TOKEN`, `NOTION_API_KEY`, and `NOTION_DATABASE_ID`.
- The local `openai-whisper`/PyTorch install is large and was not completed on
  this machine. Unit tests still run because Whisper is imported only when a
  real local transcription is requested.

## TO-DO CHECKLIST

- [x] **Anyone:** add Groq-hosted transcription, a bounded local fallback, and
  focused timeout/cache tests.
- [ ] **Anyone:** after FFmpeg is installed, run
  `https://www.instagram.com/reels/DbfsdUnvDqM/` once to create its authentic
  cached extraction.
- [ ] **Jaisika:** create/share the Groq, Hindsight (promo code `MEMHACK99`),
  Google Calendar (OAuth refresh token), and Notion keys.
- [ ] **Jaisika:** open and merge the PR for `jaisika/actions-api`.
- [ ] **Jaisika:** decide whether scholarships/exams come back and whether
  green-confidence dates should auto-add to the calendar without Accept.
- [ ] **Anyone:** fill `backend/.env`, run `seed_hindsight.py`, and confirm the
  **Memory: Hindsight Cloud** badge.
- [ ] **Anyone:** run the real end-to-end Reel test: card + Why panel → Accept
  → real calendar event + Notion page.
- [ ] **Anyone:** record the demo video and complete the content deliverables:
  article + LinkedIn post per person and one team video; never mention
  "hackathon".

## HOW TO CONTINUE

Current branch: `laaibah/demo-ready`, based on `jaisika/actions-api`.

```powershell
git fetch origin
git switch laaibah/demo-ready
git pull --ff-only
```

Activate the relevant existing environment before running a component:

```powershell
backend\api\venv\Scripts\Activate.ps1
backend\classification\venv\Scripts\Activate.ps1
backend\extraction\ocr\venv\Scripts\Activate.ps1
backend\extraction\audio\venv\Scripts\Activate.ps1
backend\actions\venv\Scripts\Activate.ps1
```

# Windows setup guide

Step-by-step setup for running TheNag's full stack on Windows, including the
optional integrations (Google Calendar, Notion, Groq, Hindsight). Everything
here matches the code as of this writing — commands were run and verified in
this repo, not guessed.

Requirements: Python 3.11+, Node.js 20+, PowerShell.

## 1. System installs: Tesseract and FFmpeg

Both are needed for real link ingestion (`POST /api/process-link`), which runs
OCR and audio transcription on the downloaded reel. They are **not** needed
for demo mode (caption paste / upload with `ENABLE_LOCAL_WHISPER=false`).

### Tesseract (with Hindi + English data)

1. Download the Windows installer from the
   [UB-Mannheim Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki)
   (the official Windows distribution referenced by the Tesseract project).
2. During install, expand **"Additional language data"** and check at least
   **Hindi** (`hin`) alongside the default **English** (`eng`). The pipeline's
   validated languages (`backend/extraction/ocr/ocr_engine.py::PHASE_1_LANGUAGES`)
   are Hindi, English, Bengali, Tamil, and Telugu — check those too (`ben`,
   `tam`, `tel`) if you want full phase-1 language coverage.
3. Add the install directory to your PATH (default:
   `C:\Program Files\Tesseract-OCR`). Open a **new** terminal afterward.
4. Verify:
   ```powershell
   tesseract --version
   tesseract --list-langs
   ```
   `--list-langs` must include `eng` and `hin`.

### FFmpeg

1. Download the "release essentials" build from
   [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (referenced in
   `backend/extraction/audio/README.md`).
2. Extract it somewhere permanent and add its `bin` folder to your PATH
   (e.g. `C:\ffmpeg\bin`). Open a **new** terminal afterward.
3. Verify:
   ```powershell
   ffmpeg -version
   ```

## 2. Environment keys

```powershell
cd backend
Copy-Item .env.example .env
```

`.env` is already gitignored (`.gitignore` and `backend/.gitignore` both list
it) — it will never be committed.

| Key | Required? | Purpose | Where to get it |
| --- | --- | --- | --- |
| `DATABASE_URL` | Only for Postgres mode | App data + shared source-trust bank connection string | Matches `docker-compose.yml`'s defaults as shipped; no external signup |
| `CORS_ORIGINS` | Optional | Allowed frontend origin(s) | Defaults to `http://localhost:5173` |
| `GROQ_API_KEY` | Optional (mock if missing) | Enables Groq-based extraction instead of the deterministic heuristic parser | [console.groq.com](https://console.groq.com) → API Keys |
| `GROQ_MODEL` | Optional | Overrides the Groq model | Defaults to `openai/gpt-oss-120b` |
| `GROQ_API_URL` | Optional | Overrides the Groq endpoint | Only needed for a custom/OpenAI-compatible endpoint |
| `HINDSIGHT_API_URL` / `HINDSIGHT_API_KEY` | Optional (mock if missing) | Private per-user memory via Hindsight Cloud instead of the in-process demo provider | Your Hindsight Cloud deployment's endpoint + credential |
| `HINDSIGHT_BANK_PREFIX` | Optional | Per-user memory bank name prefix | Defaults to `thenag-user` |
| `ENABLE_LOCAL_WHISPER` | Optional | `true` to transcribe uploaded videos via Whisper instead of a caption fallback | Not a secret — just `true`/`false` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` | Optional (mock if missing) | Real Google Calendar events on accept | See §2a below |
| `NOTION_API_KEY` / `NOTION_DATABASE_ID` | Optional (mock if missing) | Real Notion notes/pages on accept | See §2b below |

Any missing optional key falls back to a mock/deterministic provider — the
app never breaks because a key is absent.

### 2a. Google Calendar setup

`backend/actions/providers.py::GoogleCalendarProvider` uses refresh-token auth
only (no in-app OAuth flow) and always targets your **primary calendar**
(`https://www.googleapis.com/calendar/v3/calendars/primary/events` — not
configurable via env today).

1. **Cloud project:** go to the
   [Google Cloud Console](https://console.cloud.google.com/), create a project
   (or pick an existing one).
2. **Enable the API:** APIs & Services → Library → search **Google Calendar
   API** → Enable.
3. **OAuth client ID/secret:** APIs & Services → Credentials → Create
   Credentials → OAuth client ID → application type **Web application** →
   add authorized redirect URI `https://developers.google.com/oauthplayground`
   → Create. Copy the **Client ID** and **Client Secret**.
4. **Refresh token via OAuth Playground:**
   - Open the [OAuth 2.0 Playground](https://developers.google.com/oauthplayground).
   - Click the gear icon (top right) → check **"Use your own OAuth
     credentials"** → paste the Client ID/Secret from step 3.
   - In **Step 1**, enter this exact scope URL and click **Authorize APIs**:
     ```
     https://www.googleapis.com/auth/calendar
     ```
   - Sign in with the Google account whose calendar should receive events,
     and allow access.
   - In **Step 2**, click **"Exchange authorization code for tokens"**. Copy
     the **Refresh token** value.
5. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` in
   `.env`.

### 2b. Notion setup

`backend/actions/providers.py::NotionProvider.create_note()` creates a page
with exactly two properties, so the target database must have them:

- **Name** — Title property (Notion's default title column; keep it named
  exactly `Name`).
- **Status** — Select property, with these options (the only status strings
  `backend/actions/engine.py` uses): `confirmed`, `needs confirmation`,
  `uncertain category`, `note only`.

Steps:

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) →
   **New integration** → name it (e.g. "TheNag") → select your workspace →
   Create. Copy the **Internal Integration Secret** → `NOTION_API_KEY`.
2. Create a new full-page database in Notion with the **Name** and **Status**
   properties described above (Select options: `confirmed`,
   `needs confirmation`, `uncertain category`, `note only`).
3. Share the database with the integration: open the database → **"..."**
   menu → **Connections** (or **Add connections**) → select the integration
   from step 1.
4. Copy the database ID from its URL — the 32-character ID segment right
   after the workspace name and before `?v=` in
   `https://www.notion.so/<workspace>/<DATABASE_ID>?v=...`.
5. Set `NOTION_API_KEY` and `NOTION_DATABASE_ID` in `.env`.

### 2c. Groq / Hindsight (optional)

- **Groq:** sign up at [console.groq.com](https://console.groq.com), create
  an API key, set `GROQ_API_KEY`. Without it, `heuristic_extract()`'s
  deterministic parser is used — this is the default demo path and is fully
  functional on its own.
- **Hindsight:** point `HINDSIGHT_API_URL`/`HINDSIGHT_API_KEY` at your
  Hindsight Cloud deployment. Without them, `DemoMemoryProvider` (an
  in-process, seeded memory provider) is used automatically.

### 2d. Seeding history into Hindsight (optional)

Once `HINDSIGHT_API_URL`/`HINDSIGHT_API_KEY` are set, the real Hindsight banks
start empty — none of `backend/demo/seed.json`'s 21 days of fictional history
is in them yet. `backend/demo/seed_hindsight.py` retains that history (private
per-user decisions/preferences, and the shared source-trust bank) into the
real banks, preserving each seed action's original `created_at` timestamp
(folded into its retained metadata as `occurred_at`).

```powershell
cd backend\demo
..\api\venv\Scripts\python.exe seed_hindsight.py
```

It's idempotent — every retained fact carries a `seed_id`, checked via recall
before retaining, so running it again skips everything already there instead
of duplicating it. Safe to run without Hindsight configured too (seeds the
in-process demo providers instead, useful only for dry-running the script's
own logic since that state doesn't persist).

## 3. Python venvs

Each subsystem has its own venv and `requirements.txt` — don't mix them.

| Subsystem | Folder | requirements.txt | Needs |
| --- | --- | --- | --- |
| API | `backend/api` | `backend/api/requirements.txt` | fastapi/uvicorn **plus** all extraction deps below (it lazily imports `combine.py` for `/api/process-link`) |
| Classification | `backend/classification` | `backend/classification/requirements.txt` | stdlib + psycopg2 (for `db_writes.py`) + pytest |
| OCR | `backend/extraction/ocr` | `backend/extraction/ocr/requirements.txt` | pytesseract, opencv-python, Pillow, yt-dlp, instaloader, requests |
| Audio | `backend/extraction/audio` | `backend/extraction/audio/requirements.txt` | openai-whisper (pulls in PyTorch — a large, several-hundred-MB-plus download), yt-dlp, instaloader, requests |
| Extraction (combined) | `backend/extraction` | `backend/extraction/requirements.txt` | Union of OCR + audio deps — only needed to run `python combine.py` standalone; the API doesn't use this venv |
| Actions | `backend/actions` | `backend/actions/requirements.txt` | stdlib (`urllib`) + pytest only — no SDK dependency |

Create/activate each with:

```powershell
cd backend\<subsystem-folder>
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

PyTorch (via `openai-whisper`) is the one large install — budget disk space
and a few minutes for it. You only need it in `backend/extraction/audio`'s
venv and in `backend/api`'s venv (for the real `/api/process-link` path);
skip it entirely if you're only running demo mode.

## 4. Tests

| Suite | Folder | Venv | Command | Passing |
| --- | --- | --- | --- | --- |
| API | `backend/api` | `backend/api/venv` | `pytest tests -v` | 10/10 |
| Classification | `backend/classification` | `backend/classification/venv` | `pytest tests -v` | 34/34 |
| OCR | `backend/extraction/ocr` | `backend/extraction/ocr/venv` | `pytest tests -v` | 14/14 |
| Audio | `backend/extraction/audio` | `backend/extraction/audio/venv` | `pytest tests -v` | 4/4 |

The OCR and audio suites are unit tests only (no Tesseract/FFmpeg/real media
needed — see each `tests/` file's own docstring). `db_writes.py`'s tests mock
the database connection, so classification tests don't need Postgres running.

## 5. Run the app

Backend:
```powershell
cd backend\api
.\venv\Scripts\Activate.ps1
uvicorn app:app --reload --port 8000
```

Frontend (separate terminal):
```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

## 6. Smoke test checklist

1. Open the app, click **Add an opportunity** — the **Paste link** tab should
   be selected by default.
2. Paste a public Instagram Reel URL and submit.
   - **Expect:** a new opportunity card appears with extracted details and a
     working **Why this?** panel.
   - **If it fails instead:** the app should auto-switch to the **Paste
     caption** tab with an error message — this is the `AutoFetchFailed`
     fallback, not a bug. Paste the caption manually to continue, or check
     that Tesseract/FFmpeg are on PATH and `backend/api`'s venv has the
     extraction dependencies installed (§3).
3. Click **Accept** on the card.
   - **Expect (green-confidence deadline):** a calendar event appears on the
     configured Google account's primary calendar, and a Notion page appears
     in the configured database with Status "confirmed".
   - **Expect (yellow-confidence deadline, uncertain category, or no Google/
     Notion keys set):** only a Notion page (or, with no keys set, an
     in-memory mock note — check the API response's `action_result` field)
     appears, with Status "needs confirmation" or "uncertain category".
   - **If nothing appears in Google/Notion:** confirm the four/two respective
     env keys are set and `.env` was loaded (restart `uvicorn` after editing
     `.env`); check the Notion database has exactly the **Name**/**Status**
     properties from §2b and is shared with the integration; check the
     terminal running `uvicorn` for a `RuntimeError` from the provider.
