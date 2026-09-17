# Classification + Confidence (Person 2)

Takes Person 1's combined extraction output for one reel and decides
what kind of opportunity it is, how confident we are in each extracted
fact, and resolves any relative dates -- then persists the result as
the reel's `opportunities` row. See `docs/spec.md` Sections 3-4 and
`docs/team-structure.md` Section 2 for the full product requirements
this implements.

## What this does

1. **Classify** (`classifier.py`) -- scores the reel's caption,
   hashtags, OCR text and transcript against per-category keyword
   lists (`keywords.py`, covering Phase 1 languages: Hindi, English,
   Bengali, Tamil, Telugu -- see that file's docstring for a caveat on
   translation accuracy) and picks a primary category (one of Job,
   Internship, Scholarship, College/Admission, Interview, Exam,
   Hackathon/Competition, or Uncertain), plus an optional secondary
   category.
2. **Score confidence** (`confidence.py`) -- tags the category and
   each fact green/yellow/red per `docs/spec.md` Section 4. A
   low-but-nonzero classification score returns a best-guess category
   tagged red *with* clarifying questions attached, rather than either
   silently trusting it or discarding the guess entirely.
3. **Resolve dates** (`date_resolver.py`) -- parses explicit dates
   ("15 September 2026"), month ranges ("May-Jul 2026"), and relative
   expressions ("tomorrow", "in 2 weeks", "next Friday") against the
   reel's own post date. Relative dates are always tagged yellow, even
   after resolution, since they're a calculated inference, not a
   directly stated date.
4. **Persist** (`db_writes.py`) -- creates the `opportunities` row
   (`primary_category`, `secondary_categories`, `extracted_facts`),
   and moves `reels.current_stage` through
   `classifying` -> `classified` (or `failed`, with an
   `error_message`), logging a `stage_events` row at start and finish.
   See `docs/database-schema.md` for the full table reference.

## How to run it standalone

```
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Classify one extraction object without touching the database:

```python
from classifier import classify_extraction

result = classify_extraction({
    "caption_text": "Campus placement drive -- full-time hiring",
    "hashtags": ["jobs", "hiring"],
    "ocr_results": [],
    "transcript": None,
})

print(result.primary_category, result.overall_confidence)
```

Classify **and** persist to Postgres (requires the database running --
see `backend/db/README.md`):

```python
from db_writes import classify_and_persist

opportunity_id = classify_and_persist(reel_id, user_id, extraction)
```

## Input / output contract

**Input** -- the dict `backend/extraction/combine.py::run_extraction()`
returns (Person 1 -> Person 2 interface):

```
{
  "media_type": "video" | "image",
  "caption_text": str | None,
  "hashtags": [str],
  "ocr_results": [{"text": str, "timestamp": float, "confidence_level": "green"|"yellow"|"red", "raw_confidence": float}],
  "transcript": {"text": str, "detected_language": str, "segments": [...]} | None,
  "source_languages": [str],
}
```

**Output** -- `models.ClassifiedFacts`:

```
primary_category: str            # one of the 8 categories
secondary_categories: [str]
extracted_facts: [ExtractedFact]  # value, confidence, fact_type, source, evidence, timestamp
resolved_dates: [dict]            # date/date range, confidence, date_type, source
overall_confidence: "green" | "yellow" | "red"
clarification_questions: [str]    # non-empty whenever overall_confidence == "red"
```

`ClassifiedFacts.to_opportunity_row()` and `ExtractedFact.to_dict()`
shape this into the `opportunities.extracted_facts` jsonb column
format documented in `docs/database-schema.md`
(`{value, confidence, type, source}`).

## Environment variables

- `DATABASE_URL` -- only needed if you call `db_writes.py`'s functions
  (not needed for `classify_extraction()`/`resolve_dates()` alone).
  See `backend/db/README.md` / `backend/.env.example`.

## Testing

```
pytest tests/ -v
```

Covers all 7 categories + Uncertain, secondary tagging, hashtag
weighting, one non-English example per Phase 1 language, explicit and
relative date resolution, confidence-tier rules, and `db_writes.py`
against a mocked connection (no live Postgres required to run the
suite).

## Known gaps / next steps

- Keyword-based classification is a first pass, not the LLM-based
  approach `docs/team-structure.md` originally suggested -- works but
  will miss phrasing outside the keyword lists. Revisit if accuracy
  testing shows this is a real limitation.
- Native-script and transliterated keywords in `keywords.py` have not
  been reviewed by a native speaker of each language -- verify against
  real reel samples per language before trusting in production, same
  as the caveat already applied to Whisper's output in
  `docs/engineering-decisions.md`.
- Only Phase 1 languages have keyword coverage. Phase 2/3 languages
  (Marathi, Gujarati, Kannada, Malayalam, Odia, Urdu) are out of scope
  for v1 per `docs/team-structure.md` Section 7.
