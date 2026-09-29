# TheNag team structure

The repository identifies four roles but does not identify individual names. The content kit therefore provides one labelled reusable template for each role.

| Role | Ownership | Core output |
| --- | --- | --- |
| Ingestion + extraction | Upload/caption intake, OCR, Whisper handoff | Structured opportunity evidence |
| Classification + confidence | Opportunity category and extraction confidence | Jobs & Gigs, Interviews & Hiring Drives, or Uncertain |
| Memory + trust | Duplicate/change detection, source trust, private memory | Explainable ranking and safe memory retention |
| Frontend | React intake, opportunity cards, Why panel, Weekly Reflect | Clear job-seeker workflow |

## Current flow

```text
Caption or video → extract evidence → recall private preferences
→ compare prior opportunities → classify → combine extraction and source trust
→ rank → recommend a draft-only next step → retain a redacted decision memory
```

## Product principles

1. The user remains in charge; TheNag never submits an application.
2. One rejected listing does not permanently hide a role.
3. Source trust needs multiple observations and supporting evidence.
4. Private user memory is isolated by user and never becomes B2B data.
5. Missing credentials must result in a working, clearly labelled demo fallback.
