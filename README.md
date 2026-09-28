# TheNag

Share an Instagram Reel about a job, internship, scholarship, college admission, interview, exam, or hackathon — get a verified deadline, a document checklist, and a prep plan, instead of a saved post you'll never revisit.

## What this is

Not a general "organize your saved Reels" tool — there are already several of those (Hako, Gemlyst, Acted). TheNag is specifically an **educational/early-career opportunity assistant**, built narrower and deeper for students who save deadline-critical content on Instagram and then forget about it.

## How it works

1. **Share a reel** to the app (via Instagram's native share sheet, a pasted link, or a direct upload) — there's no way to read a user's Saved folder automatically, so this is always user-initiated.
2. **Extraction** pulls out everything relevant: caption text, hashtags, on-screen burned-in text (OCR), and spoken audio (transcribed via Whisper), across 11 Indian languages.
3. **Classification** figures out what kind of opportunity it is — Job, Internship, Scholarship, College/Admission, Interview, Exam, Hackathon/Competition, or Uncertain — and tags every extracted fact with a confidence level (green/yellow/red), so nothing gets silently guessed.
4. **Verification** cross-checks the claimed deadline against the actual official notice where one can be found, surfacing any conflict explicitly rather than trusting either source blindly.
5. **Action** creates exactly one calendar event per opportunity, with a notes object carrying the checklist, required documents, milestones, and category-specific detail (like team size and location for a hackathon) — never a cluttered pile of separate calendar entries.
6. **Confirmation** closes the loop: the user gets a summary of what was added, a one-time "check your note" nudge, and reminder alerts they can mute per opportunity.

## Project docs

- [`docs/spec.md`](docs/spec.md) — the full product spec
- [`docs/team-structure.md`](docs/team-structure.md) — team roles, ownership, and interfaces
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to clone, branch, commit, and open a PR

## Team

3 backend, 1 frontend. See `docs/team-structure.md` for who owns what.

## Status

In active development.


TheNag/
├── README.md
├── CONTRIBUTE.md
├── docs/
│   ├── spec.md                          (the full product spec)
│   └── team-structure.md                (the team structure doc)
│
├── backend/
│   ├── extraction/                      (Person 1a + 1b)
│   │   ├── ocr/                         (Person 1a)
│   │   │   ├── frame_extraction.py
│   │   │   ├── ocr_engine.py
│   │   │   └── tests/
│   │   ├── audio/                       (Person 1b)
│   │   │   ├── transcription.py         (Whisper)
│   │   │   ├── caption_hashtag.py
│   │   │   └── tests/
│   │   ├── normalize.py                 (the shared merge step — Step 0 contract lives here)
│   │   └── contracts/
│   │       └── extraction_schema.md     (the agreed object shapes from Step 0)
│   │
│   ├── classification/                  (Person 2)
│   │   ├── classifier.py
│   │   ├── confidence.py
│   │   ├── date_resolution.py
│   │   └── tests/
│   │
│   ├── actions/                         (Person 3)
│   │   ├── verification.py              (official-source check)
│   │   ├── deadline_typing.py
│   │   ├── category_actions.py          (per-category notes generation)
│   │   ├── calendar.py
│   │   ├── milestones.py
│   │   ├── notifications.py
│   │   └── tests/
│   │
│   ├── api/                             (the orchestration layer tying extraction → classification → actions together, and exposing it to frontend)
│   │   ├── routes.py
│   │   └── models.py
│   │
│   ├── docker-compose.yml               (local Postgres — run `docker compose up -d` from backend/)
│   └── .env.example
│
├── frontend/                            (Person 4)
│   ├── src/
│   │   ├── screens/
│   │   │   ├── ShareIntake/
│   │   │   ├── ReviewConfirm/
│   │   │   ├── NotesView/
│   │   │   └── NotificationSettings/
│   │   └── components/
│   └── tests/
│
├── .gitignore
└── requirements.txt / package.json      (per your final stack choice)