# TheNag product specification

## Positioning

TheNag is a memory-driven job opportunity assistant for working professionals and job seekers. It reduces alert fatigue by learning from what a user saves, accepts, rejects, and skips.

**Promise:** Alerts give you more listings. TheNag gives you fewer, better ones—because it remembers.

## Supported demo flow

1. Paste a reel/post link, upload a video, or paste a caption in English, Hindi, or Hinglish.
2. Extract the available title, company, location, work mode, type, skills, experience, compensation, deadline, link, creator, and evidence. For link input, category and per-date confidence come from the classifier; the rest comes from running the same heuristic extraction over the combined caption/OCR/transcript text.
3. Recall only the submitting user’s private preferences and prior decisions.
4. Detect an exact duplicate, updated listing, similar listing from another source, or a new opportunity — link-ingested opportunities go through the same duplicate check, ranking, and Why panel as caption/upload input.
5. Classify as Jobs & Gigs, Interviews & Hiring Drives, or Uncertain.
6. Combine extraction confidence with shared source-trust history.
7. Rank and explain a draft-only next action. Never apply automatically.
8. Retain a redacted decision summary so a future recommendation can improve.
9. On accept: a green-confidence date gets a calendar event and a confirmed note; a yellow-confidence date, an uncertain category, or missing confidence gets a note only, marked "needs confirmation" where relevant. A duplicate of an opportunity the user already accepted updates that opportunity's existing event and note instead of creating new ones.

## Explainability requirements

Every card must offer a Why panel that tells the user:

- which remembered preferences affected rank;
- whether they saw the listing earlier and what changed;
- the source observation count and reliability evidence;
- how extraction and source confidence combine;
- why a listing was recommended or deprioritized.

## Privacy requirements

- User memory is private and scoped by user id.
- Emails and phone numbers are redacted before memory retention.
- The user can inspect and manage remembered preferences.
- Source trust is aggregate product data. It never contains private user decisions or memory text.
- B2B verified feeds use shared source/opportunity information only, never user history.

## Demo data requirements

The seed includes 28 fictional opportunities across technical and non-technical jobs, freelance work, internships, interviews, remote and on-site roles, English/Hindi examples, incomplete listings, duplicates, changed deadlines, and an unreliable source. Three weeks of decisions make Weekly Reflect meaningful.

## Roadmap

- Instagram share-sheet integration (direct Reel-link ingestion is implemented — see `POST /api/process-link`)
- Additional Indian languages
- Scholarship and exam flows
- Official-source verification at scale
- Durable production persistence and user authentication
