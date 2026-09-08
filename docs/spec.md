# Educational Opportunity Assistant — Product Spec

**One-line pitch:** Share an Instagram Reel about a job, internship, scholarship, college admission, interview, exam, or hackathon — get a verified deadline, a document checklist, and a prep plan, instead of a saved post you'll never revisit.

**Positioning:** Not a general "organize your saved Reels" tool (Hako, Gemlyst, Acted already own that space). This is specifically an **educational/early-career opportunity assistant** — narrower, deeper, and built for students who save deadline-critical content and forget about it.

---

## 1. Input Flow

Instagram has no public API for reading a user's private Saved folder or collections — confirmed, not assumed. So input must be **user-initiated**, never silent background monitoring.

**Supported input methods (v1):**
- Share a Reel to the app via Instagram's native Share sheet (primary path)
- Paste a Reel link directly into the app
- Upload a video file or screen recording
- Upload a screenshot
- Paste caption text manually

**Explicitly not supported:** reading a user's Instagram Saved folder automatically, or requesting Instagram login credentials.

Caption text and hashtags are captured at this stage alongside the reel itself, and carried through as metadata for the extraction and classification steps (see Section 2) — hashtags in particular are a strong, low-cost signal for classification (e.g., `#hackathon`, `#scholarship2026`, `#campusplacement`) that shouldn't be discarded after input.

---

## 2. Extraction Pipeline

Every input is processed through up to four extraction sources, combined into one unified text representation before classification:

1. **Caption text** — direct extraction, straightforward
2. **Hashtags** — extracted as their own signal alongside the caption, not discarded; passed through as metadata to the classification step (Section 3) since tags like `#hackathon`, `#scholarship2026`, or `#campusplacement` are a strong, low-cost classification hint
3. **On-screen burned-in text (OCR)** — since a lot of deadline info lives in video overlay text, not the caption
4. **Audio transcription** — via Whisper, for any spoken content in the reel

### Language support (locked, 11 languages)

Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu, Kannada, Odia, Malayalam, English

**Phased rollout, not simultaneous full quality:**
- **Phase 1 (launch):** Hindi, English, Bengali, Tamil, Telugu — highest speaker populations, best current-tooling coverage
- **Phase 2:** Marathi, Gujarati, Kannada, Malayalam, Odia
- **Phase 3:** Urdu (right-to-left script — genuinely different technical handling from the rest of the list, treated as its own workstream, not "one more language")

**Known technical reality, not a blocker:** Whisper transcription should perform reasonably across all 11. OCR reliability will vary significantly by script (8 distinct scripts across this list: Devanagari, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Perso-Arabic, Latin) — weaker-OCR languages don't block launch, they just default to lower confidence scores until validated (see Section 4).

Code-switching (e.g., Hindi-English mixed captions) is treated as the default case, not an edge case, in both extraction and classification prompts.

---

## 3. Classification

Every processed reel gets:
- **One primary category** — drives the main action
- **Optional secondary category tag(s)** — trigger additional smaller actions (e.g., primary: Scholarship, secondary: Interview → document checklist now, interview prep task once an interview is actually scheduled)

Classification runs on the full combined extraction output (Section 2), including caption and hashtag metadata carried through from input — hashtags in particular often make the primary category unambiguous even before OCR/transcription finish processing, so they're weighted as a meaningful signal, not just supplementary text.

### Locked categories (8 total: 7 real + Uncertain)

| Category | Scope | Output |
|---|---|---|
| **Job** | Full-time/part-time postings, campus placements, fresher hiring | Deadline (if any) + application link/checklist + resume/prep checklist |
| **Internship** | Internship postings, application windows | Deadline + eligibility summary + application checklist |
| **Scholarship** | Scholarship announcements, financial aid | Deadline + eligibility summary + document checklist |
| **College/Admission** | College applications, entrance exam registration, admission deadlines | Application timeline + document checklist + fee deadline (if mentioned) |
| **Interview** | Job/admission/scholarship interviews | Calendar event + prep checklist (research, question prep) |
| **Exam** | Competitive exams, entrance tests, certification exams, semester/board exams, government exams | Calendar event with the exam date as the event, and required documents listed in the event description + study/prep checklist |
| **Hackathon/Competition** | Hackathons, coding/case/academic competitions | Calendar event for the deadline, with the event description containing location (online/city/venue), team size requirement, and domain/theme, pulled from the reel + team/submission checklist |
| **Uncertain** | Can't confidently classify | Extracted facts + source evidence + 1-2 clarifying questions, no auto-action |

**Explicitly out of scope:** general life-admin categories (e.g., driving tests) — the product is deliberately education/career-launch only, not a general reminder tool.

### 3.1 One calendar event per opportunity, notes carry the rest

Rather than creating a separate calendar entry per milestone/reminder/checklist item (which clutters the user's calendar fast once several opportunities are being tracked), the design is: **one calendar event per opportunity**, tied to the actual deadline/event date. Everything else — checklists, required documents, milestones, hackathon-specific details — lives in a **notes** object attached to that event, not as additional calendar entries.

Category-specific note content:
- **Hackathon/Competition:** location (online / city / venue), team size requirement, domain/theme
- **Exam (including government exams):** required documents for the exam/application
- Other categories carry their respective checklist/eligibility/document info in notes the same way, per Section 3's output column

More categories can get deeper note-field extraction as quality is validated — Hackathon and Exam are the ones explicitly specified so far.

### 3.2 Reminder timing

Default reminder cadence: **one week ahead of the actual event/deadline**, in addition to the confirmation message sent immediately after the reel is processed (Section 6). This is a notification/reminder against the single calendar event from 3.1 — not a second calendar entry. If a category's backward milestone plan (Section 5.4) provides earlier, more specific milestones, those live in the same notes object and supersede the generic one-week reminder rather than stacking a separate alert on top of it.


---

## 4. Confidence-Level System (core differentiator)

Every extracted fact (date, name, eligibility detail, etc.) is tagged with a confidence level:

- 🟢 **Green** — clear, confirmed, high-confidence extraction
- 🟡 **Yellow** — incomplete or uncertain. For relative dates (e.g., "next Friday," "in 2 weeks"), the system uses the reel's own post date as the reference point and calculates the actual date from it — this resolved date still gets flagged yellow rather than green, since it's a calculated inference, not a directly stated date, and the reel's post date itself is a proxy the user should be able to double check. OCR on a lower-confidence script is also yellow by default until validated for that language.
- 🔴 **Red** — conflicting or unreadable information

**Hard rule:** a red-confidence date is never auto-added to a calendar. It always routes to user confirmation first. This mirrors the same "don't guess, escalate to human" principle used in the Razorpay agent's approval-gate design — consistent philosophy across both products.

---

## 5. Category-Specific Actions

Actions are generated per the table in Section 3. All actions are created only after confidence checks pass (or after user confirms a yellow/red-flagged fact).

### 5.1 Verification against official sources (moved into v1)

For any extracted deadline, the system attempts to locate the actual official notice/webpage for the opportunity and cross-checks the reel's claimed date against it. If the two disagree, the conflict is surfaced explicitly rather than silently trusting either source:
> "Reel: Sept 15 / Official notice: Sept 18"
The user picks which date to use before anything is added to a calendar. If no official source can be found, the reel's date is used as-is but flagged accordingly (see Section 4 confidence levels).

### 5.2 Evidence tagging per fact (moved into v1)

Every extracted fact shows exactly where it came from:
- Caption
- On-screen text (with timestamp in the reel)
- Speech (with timestamp in the reel)
- Official source link (when verification in 5.1 finds one)

This lets the user quickly check any fact against its origin rather than trusting the extraction blindly.

### 5.3 Deadline-type awareness (moved into v1)

The system distinguishes between different kinds of dates rather than treating everything as one generic "deadline":
- Application opening
- Application closing
- Fee-payment deadline
- Correction window
- Interview date
- Examination date
- Admit-card release
- Result announcement
- Rolling application / "apply as soon as possible"

Each category's output (Section 3) uses the relevant deadline type(s) rather than a single undifferentiated date field.

### 5.4 Backward milestone planning (moved into v1)

Once a deadline is confirmed, the system auto-suggests earlier prep milestones counting back from it — for example, for a scholarship: 30 days out (request recommendation letters), 21 days out (collect official documents), 14 days out (finish first essay draft), 7 days out (complete application), 2 days out (submit). Milestones are category-appropriate, not identical across all types. Per Section 3.1, these milestones live inside the single calendar event's notes object as a checklist/timeline, rather than each milestone becoming its own separate calendar entry.

---

## 6. Confirmation Loop (core differentiator)

After any action is taken, the user receives a clear summary:
> "Added: Rhodes Scholarship deadline, Nov 15 (🟢 confirmed) — want a reminder 3 days before?"

This closes the loop that silent calendar-entry creation (what most competitors do) doesn't — it's also the actual demoable "wow" moment, since a judge/user can't verify a silent action but can see a confirmation happen live.

### 6.1 Two distinct notification types

**Note-ready notification:** pushed once processing finishes, prompting the user to check the note the app just created for that reel (e.g., "We made a note for your Scholarship reel — tap to check it out"). Tapping deep-links to that opportunity's note. This fires once per reel, right after Section 6's confirmation is generated — it's the push-notification form of the confirmation loop, not a separate feature.

**Deadline/reminder alerts:** the recurring reminders from Section 3.2 (one week ahead, plus any backward-milestone alerts from 5.4). These are **opt-out per opportunity, not just globally** — the user can turn off reminders for one specific tracked reel (e.g., a hackathon they decided not to enter) without disabling notifications for everything else they're tracking. The note-ready notification above is not covered by this per-opportunity toggle, since it only fires once and isn't a recurring reminder.

---

## 7. V2 Roadmap (not in initial build — real differentiators, sequenced for later)

- **Multiple linked outputs per opportunity** — a scholarship produces deadline + eligibility + documents + essay task + progress tracker, not just one entry
- **Change monitoring** — watch the official source after creation for deadline extensions or changes
- **Duplicate/conflict handling** — merge multiple reels about the same opportunity instead of duplicating
- **India-specific document recognition** — recognize document types (Aadhaar, mark sheets, income certificate, domicile certificate, etc.) for checklist generation

---

## 8. Explicitly Out of Scope (v1 only)

- **Fully autonomous "apply on the user's behalf."** Application forms have no common schema across platforms, tailored content (resumes/essays) genuinely affects real outcomes, and the failure mode (a bad or wrongly-submitted application) is high-stakes in a way a missed reminder isn't. This is a v1 exclusion, not a permanent one — [ApplyPilot](https://github.com/Pickle-Pixel/ApplyPilot) is a useful reference architecture (discover → enrich → score → tailor → cover-letter → apply) if this gets revisited later, though its fully autonomous auto-submit mode has real risks worth noting (CAPTCHA failures fail silently, and most job/ATS platforms' terms of service prohibit automated submission) — its own "discovery + tailoring only" mode is closer to what a human-in-the-loop version here would look like.
- Reading Instagram's Saved folder automatically (no API access exists for this)
- Requesting Instagram login credentials

---

## 9. Known Competitive Landscape (why this is still differentiated)

Closest existing products — Hako, Gemlyst, Acted, Fabric — already do "watch content → classify → category-specific output," so that pattern alone isn't novel. None of them:
- Focus specifically on education/career opportunities (they're general lifestyle organizers — recipes, travel, fitness)
- Have a confidence-level/uncertainty system
- Generate education-specific outputs (document checklists, eligibility summaries, prep plans)
- Support this depth of Indian-language coverage

The differentiation is **opportunity specialization + verification/confidence handling + depth of category-specific action**, not the underlying "classify and route" pattern itself.
