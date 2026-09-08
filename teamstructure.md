TheNag — Four-Person Team Structure, Responsibilities & System Interfaces
Problem Statement: Extract job, internship, scholarship, exam, interview, and hackathon deadlines from shared Instagram Reels across 11 Indian languages, and turn them into verified calendar events with actionable notes.

This document defines the recommended four-person structure for a first working prototype. The team is divided into three backend/intelligence roles and one frontend role so that every member owns a complete subsystem while the interfaces between subsystems remain clear.

| Person | Role | Primary Ownership | Main Output |
|---|---|---|---|
| 1 | Ingestion + Extraction Engineer | Input handling, caption/hashtag extraction, OCR, audio transcription | Structured, multilingual extraction output |
| 2 | Classification + Confidence Engineer | Category classification, secondary tagging, confidence scoring | Classified, confidence-scored facts |
| 3 | Actions + Verification Engineer | Verification, deadline typing, calendar/notes generation, notifications | Verified calendar event + notes |
| 4 | Frontend Engineer | Share intake UI, review/confirm screens, notes view, notification settings | Student-facing application |

---

## 1. Person 1 — Ingestion + Extraction Engineer

Owns everything from a shared reel arriving in the system to a clean, unified block of extracted text and metadata.

**Core pipeline**
Reel Share/Upload → Input Handling → Caption + Hashtag Extraction → OCR (on-screen text) → Audio Transcription (Whisper) → Combined Extraction Output

| Area | What the person actually does |
|---|---|
| Input handling | Accept share-sheet input, pasted links, video uploads, screenshots, and pasted caption text |
| Caption/hashtag extraction | Pull caption text and hashtags as separate, distinct signals, not merged together |
| OCR | Extract burned-in on-screen text from video frames across 8 distinct scripts |
| Audio transcription | Transcribe spoken content via Whisper across the 11 supported languages (phased rollout) |
| Multilingual handling | Manage code-switching (e.g., Hindi-English mixed captions) as the default case, not an edge case |
| Confidence scoring input | Flag per-source reliability, especially for lower-confidence scripts, feeding Person 2's confidence system |
| Output normalization | Combine caption, hashtags, OCR, and transcript into one unified structured object per the extraction contract |
| Evaluation | Test extraction quality per language and per category on real and realistic reel samples |

**Suggested stack:** Python, Whisper, an OCR engine (Google Cloud Vision or Tesseract), FFmpeg for frame extraction, a share-target/upload handler

**Research question:** How reliably can deadline-relevant information be extracted from a reel across captions, on-screen text, and speech, across 11 Indian languages and 8 distinct scripts?

---

## 2. Person 2 — Classification + Confidence Engineer

Determines what kind of opportunity a reel represents, and exactly how much the system should trust each extracted fact.

**Core pipeline**
Combined Extraction Output → Category Classification (Primary + Secondary) → Confidence Tagging (Green/Yellow/Red) → Relative Date Resolution → Classified, Confidence-Scored Facts

| Area | What the person actually does |
|---|---|
| Category classification | Route each reel into one of 7 categories (Job, Internship, Scholarship, College/Admission, Interview, Exam, Hackathon/Competition) or Uncertain |
| Secondary tagging | Apply secondary category tags when a reel genuinely spans two categories (e.g., Scholarship + Interview) |
| Confidence scoring | Tag every extracted fact green, yellow, or red per the locked confidence rules |
| Relative date resolution | Resolve relative dates ("next Friday") against the reel's own post date, tagged yellow, not green |
| Hashtag-weighted classification | Use hashtags as a strong, fast classification signal, not just supplementary text |
| Uncertain handling | Generate 1-2 clarifying questions when classification confidence is genuinely low, instead of guessing |
| Evaluation | Test classification accuracy across all categories and all supported languages |

**Suggested stack:** An LLM API for classification/reasoning, a prompt-evaluation framework, Python

**Research question:** Can multilingual, code-switched, hashtag-and-caption-weighted classification reliably distinguish 7 opportunity categories with well-calibrated confidence?

---

## 3. Person 3 — Actions + Verification Engineer

Turns a classified, confidence-scored reel into a real, verified calendar event, a notes object, and the right notifications.

**Core pipeline**
Classified Facts → Official-Source Verification → Deadline-Type Tagging → Category Action Generation → Single Calendar Event + Notes → Confirmation + Notifications

| Area | What the person actually does |
|---|---|
| Official-source verification | Search for the actual official notice and cross-check the reel's claimed date against it, surfacing conflicts explicitly |
| Deadline-type tagging | Distinguish application opening/closing, fee deadline, correction window, interview date, exam date, admit-card release, result date, and rolling applications |
| Category action generation | Build the category-specific notes content — team size/location/domain for hackathons, required documents for exams, eligibility/documents for scholarships, etc. |
| Calendar integration | Create exactly one calendar event per opportunity, never one per milestone |
| Backward milestone planning | Generate category-appropriate prep milestones counting back from the deadline, stored in the notes object |
| Confirmation logic | Generate the post-processing summary message shown to the user |
| Notification logic | Fire the one-time note-ready notification, and the recurring reminder alerts (opt-out per opportunity) |
| Evaluation | Verify no red-confidence fact is ever auto-added to a calendar without explicit user confirmation |

**Suggested stack:** A calendar API (Google Calendar), a push notification service (FCM/APNs), web search/fetch tooling for verification, Python or Node backend

**Research question:** Can a system verify and act on opportunity deadlines safely — surfacing conflicts and requiring human confirmation rather than silently trusting a single source?

---

## 4. Person 4 — Frontend Engineer

Builds the student-facing application for sharing reels, reviewing what was extracted, and managing reminders.

**Core pipeline**
Backend APIs → Mobile/Web UI → Share Intake + Review Screen + Notes View + Notification Settings

| Area | What the person actually does |
|---|---|
| Share intake | Receive shared reels via the OS share sheet, pasted link, or direct upload |
| Review/confirm screen | Display extracted facts with their confidence color and evidence source (caption/on-screen/speech/official) |
| Conflict resolution UI | Let the user pick between the reel's date and the official source's date when they disagree |
| Notes view | Display the checklist, milestones, documents, and category-specific detail for each tracked opportunity |
| Confirmation display | Show the post-processing summary after each reel is handled |
| Notification settings | Provide a per-opportunity mute toggle, separate from global notification settings |
| Calendar linkage | Show and deep-link to the created calendar event |

**Suggested stack:** React Native or Flutter for mobile, or React web with share-target support, a component/design library

**Research question:** How can extracted uncertainty — confidence levels, source conflicts — be presented clearly enough that a student actually trusts and acts on it?

---

## 5. Interfaces Between Team Members

Each person should expose a stable data contract early. Integration should begin before any single module is considered finished.

| Interface | Object | Minimum information |
|---|---|---|
| Person 1 → Person 2 | Extraction output | caption_text, hashtags[], ocr_text[with timestamp], transcript[with timestamp + detected language], source_languages[] |
| Person 2 → Person 3 | Classified fact set | primary_category, secondary_categories[], extracted_facts[{value, confidence, type, source}], resolved_dates |
| Person 3 → Person 4 | Application API | opportunity object (calendar_event_id, notes, confidence-tagged facts, verification conflicts, milestones), notification_preferences |

---

## 6. End-to-End Data Flow

```
SHARED REEL
   ↓
Person 1: Input handling + caption/hashtag extraction + OCR + Whisper transcription
   ↓
Extraction Output: combined text, multilingual, source-tagged
   ↓
Person 2: Classification + secondary tagging + confidence scoring + date resolution
   ↓
Classified Facts: category = Hackathon, confidence = green (team size), yellow (deadline)
   ↓
Person 3: Official-source verification + deadline typing + action generation
   ↓
Verified Opportunity: one calendar event + notes object + milestones
   ↓
Person 3: Confirmation message + note-ready notification + reminder scheduling
   ↓
Person 4: Review screen, notes view, calendar linkage, notification settings
```

---

## 7. Recommended Version-1 Scope

| Build first | Do not prioritize yet |
|---|---|
| Phase 1 languages: Hindi, English, Bengali, Tamil, Telugu | Phase 2/3 languages: Marathi, Gujarati, Kannada, Malayalam, Odia, Urdu |
| Core extraction pipeline (caption + hashtags + OCR + transcription) | Perfect OCR across all 8 scripts simultaneously |
| Classification across all 7 categories + Uncertain | Multiple linked outputs per opportunity (essay tasks, progress trackers) |
| Confidence-level system (green/yellow/red) | Change monitoring on official sources after creation |
| Official-source verification for 1-2 categories first (e.g., Scholarship) | Full verification coverage across all 7 categories on day one |
| One calendar event + notes object per opportunity | Duplicate/conflict handling across multiple reels for the same opportunity |
| Fixed-template backward milestones (e.g., 30/14/7/2 days out) | Fully dynamic, category-adaptive milestone planning |
| Confirmation loop + note-ready notification + per-opportunity reminder toggle | Fully autonomous "apply on the user's behalf" |

---

## 8. Final Ownership Model

- **Person 1:** What did the reel actually say?
- **Person 2:** What kind of opportunity is this, and how sure are we?
- **Person 3:** What should happen about it, and can we trust the date?
- **Person 4:** How does a student actually use this?

---

## 9. Project Differentiator

The proposed structure deliberately makes this more than a generic "save and summarize" reel organizer. The research and engineering core is a confidence-aware, verification-driven opportunity pipeline. A reel's claimed deadline is treated as one source of evidence rather than absolute truth — it gets cross-checked against official sources where possible, and any date the system isn't confident about is surfaced for human confirmation rather than silently trusted. The system exposes verified and unverified information separately, creating a stronger foundation for the actions students actually take: preparing documents, tracking milestones, and not missing a deadline that a saved reel would otherwise let them forget.

For the first version, the team should validate this core idea on a small, real set of shared reels across the 5 Phase 1 languages. The backend subsystems should be built around the stable interfaces above so the prototype can later expand toward the full 11-language, fully-verified version described in the product spec.