# TheNag — Engineering Decisions Log

This tracks technical decisions made during actual implementation and testing — not the product spec (see `docs/spec.md`), but the "why did we build it this specific way" record. Useful for anyone joining the project later, or for future-you wondering why something isn't done the "obvious" way.

---

## OCR engine: Tesseract (not Google Cloud Vision) — locked

**Decision:** stick with Tesseract for OCR, don't switch to Google Cloud Vision.

**Why:** Tesseract is already working reasonably well after tuning — real reel testing got clean 90%+ confidence results on genuine content. Cloud Vision would likely perform better on messier/stylized text and needs no preprocessing, but costs money past 1,000 free images/month, requires Google Cloud setup (billing, service account key), needs an internet connection per image, and would require re-validating all the thresholds and logic already tuned against Tesseract's specific confidence numbers.

**Revisit if:** accuracy becomes a real blocker — especially once Bengali/Tamil/Telugu are tested in native script (not yet done), where Tesseract may perform worse than on the Hindi-in-Latin-script + English content tested so far.

---

## Image preprocessing: OFF by default — locked

**Decision:** don't run grayscale/CLAHE/adaptive-threshold preprocessing before OCR.

**Why:** this was implemented expecting it to help (a reasonable, well-established technique in general), but real reel testing showed it made results measurably *worse* — lower confidence scores, extra garbled characters, and in one case, an entire sentence disappearing that had previously OCR'd cleanly. Likely cause: adaptive thresholding reacts to JPEG compression artifacts and photographic backgrounds as if they were text, on this kind of compressed video-frame content.

**Where it lives:** `preprocess.py` still exists and is toggleable (`use_preprocessing=True`) in case it helps on different footage later — just don't assume it helps without testing against real samples first.

---

## OCR language mode: combined string, not per-language — locked

**Decision:** run Tesseract with all Phase 1 languages combined in one call (e.g. `hin+eng+ben+tam+tel`), not each language separately with the best result kept.

**Why:** running languages separately was tried, expecting it to reduce cross-script confusion on frames with no real text. It backfired on **bilingual frames** (very common in this content — e.g. a government ministry banner showing both Hindi and English simultaneously), where running Hindi-only or English-only on a mixed frame caused whichever script wasn't targeted to be read as garbage, producing a worse result than one combined-language call reading both scripts correctly at once.

---

## Red-confidence results: dropped entirely, not passed forward — locked

**Decision:** any OCR result scoring red confidence is discarded before it reaches the pipeline's output — never passed downstream tagged as "untrustworthy," just removed.

**Why:** a garbled, low-confidence string has no value to Person 2's classifier even with a warning label attached. Confirmed on real reels — early testing showed nonsense mixed-script noise (from frames with no real text) getting tagged red correctly, but there was no reason to keep it in the output at all.

---

## Near-duplicate deduplication: word-overlap, not character-sequence — locked

**Decision:** two consecutive OCR results are treated as the same underlying text if they share ≥60% of their words (relative to the smaller reading's word count) — not based on raw character-by-character similarity.

**Why:** reels show the same on-screen text across many frames, and OCR reads each occurrence slightly differently. An initial character-sequence-based approach (`difflib.SequenceMatcher`) failed to merge readings where one had significantly more surrounding noise text than another, even though a human could see they were the same sentence. Word-overlap comparison correctly catches this — confirmed by comparing before/after on real reel output (one cluster of near-identical readings collapsed from ~10 entries to 1).

---

## URL input: best-effort, not guaranteed, with graceful fallback — locked

**Decision:** support pasting an Instagram URL as input, using yt-dlp for videos/Reels and instaloader for photo posts — but treat this entire path as best-effort, not reliable infrastructure.

**Why:** neither tool is an official Instagram API. Checked directly: Meta's own official oEmbed API no longer returns a downloadable image URL at all (deprecated Nov 2025), and its terms explicitly prohibit extracting/persisting content for anything beyond rendering an embed — so there's no fully compliant official path to this feature at all. Anonymous (non-logged-in) access via yt-dlp/instaloader can get rate-limited or blocked by Instagram at any time. Logging in was explicitly ruled out earlier (see `spec.md` Section 8 — never request Instagram credentials).

**What this means practically:** video Reel URLs work reliably. Photo post URLs work *sometimes* — when auto-fetch fails, the code raises a specific `AutoFetchFailed` exception with a clear message, and the real app should catch this and prompt the user to upload the file manually instead. Manual upload always works regardless of what Instagram does, and is the reliable fallback for every input type.

**Known unsupported case:** multi-image carousels — not handled at all yet. A user sharing a carousel should be told to share one image from it directly, or upload manually.

---

## Video download format: explicit video+audio merge, not a single combined selector — locked

**Decision:** `yt-dlp`'s format selector is `"bestvideo+bestaudio/best"` with `"merge_output_format": "mp4"`, not the simpler `"mp4/best"`.

**Why:** confirmed via a real bug — a YouTube Shorts test download succeeded with a plain `"mp4/best"` selector, but the resulting file had a video stream and **no audio stream at all** (confirmed with `ffprobe`), because that platform serves video and audio as separate streams and no single combined mp4 format existed. This failed silently until Whisper tried to read it. Forcing an explicit video+audio merge via FFmpeg fixes this for any platform that splits streams, not just YouTube — worth keeping even though Instagram reels (the actual target) seem to bundle streams together already, since it's a low-cost safeguard against the same failure on other platforms.

---

## Whisper model size: "medium", not "small" — locked

**Decision:** default Whisper model is `"medium"`, not the originally-planned `"small"`.

**Why:** confirmed via real testing, not assumption. On real reel audio with background music, `"small"` produced fluent-sounding but hallucinated garbage (random mixed Chinese/German-looking fragments with no relation to the actual content). The exact same audio, run through `"medium"`, produced a structurally coherent, grammatically correct transcript. This is a decisive difference, not a marginal one — `"small"` is not considered usable for this content type.

**Still unverified:** whether `"medium"`'s output is actually *correct* content-wise (a native speaker needs to confirm), only that it's structurally coherent where `"small"` wasn't. `"medium"` is also a much larger download (~1.4GB) and slower to run — worth knowing if this becomes a real constraint later.

**Also confirmed:** music/song content reliably produces empty transcripts regardless of model size — Whisper is built for speech, not sung vocals. Expected behavior, not a bug, and unlikely to matter for TheNag's actual target content.

**2026-09-29 demo-safety note:** the locked comparison remains valid for
transcript quality, but it is superseded for the live-demo fallback. Local
CPU transcription now uses `small` in a separate process with a 60-second
hard timeout; after that timeout the transcript is omitted and caption + OCR
continue. When `GROQ_API_KEY` is configured, the app uses Groq's hosted
Whisper-compatible transcription endpoint instead, avoiding the local CPU
path. Re-evaluate the quality tradeoff with native-speaker validation before
using this fallback for production decisions.

---

## Caption and hashtag extraction: only available for URL input, not local files — locked

**Decision:** `caption_text` and `hashtags` are populated from the source post's metadata (`yt-dlp`'s `description` field for videos, `instaloader`'s `Post.caption` for photos) only when the input is an Instagram URL. Local-file input always returns `None`/`[]` for these fields.

**Why:** there's no metadata to extract from a bare video/image file sitting on disk — captions and hashtags only exist as properties of the actual Instagram post, which is only visible when fetching by URL.

**Confirmed working via real test:** a real Instagram Reel URL correctly returned its full caption (including the actual stated deadline, "20th October") and correctly parsed hashtags (`['india', 'govtinternship', 'career', 'job', 'internship']`). Caption text is often the cleanest, most directly usable source of deadline information — frequently clearer than what OCR or the audio transcript produce from the same reel — and should be weighted accordingly once Person 2's classifier is built.

---

## Combined extraction pipeline (OCR + Whisper + caption/hashtags): confirmed working end-to-end — locked

**Decision:** `backend/extraction/combine.py` is the single entry point Person 2 should call — it downloads (if given a URL), runs OCR, runs Whisper (video only), and returns one unified object per `backend/extraction/contracts/extraction_output.md`.

**Confirmed via real test:** a real Instagram Reel URL produced correct caption text, correct hashtags, 22 OCR segments (mixed confidence, as expected — this varies reel to reel), and a coherent English transcript, all in one call, on real content.

**One real gap surfaced by this integration, not present in either subsystem alone:** `combine.py` requires *both* OCR's and audio's dependencies simultaneously (Tesseract, OpenCV, Whisper, yt-dlp, instaloader, etc.), so it needs its own dedicated venv and `requirements.txt` at `backend/extraction/` — it cannot simply reuse either subsystem's own venv, since neither has both sets of packages installed.

---

## Bug fix: relative dates now resolve against the reel's post date, not classification time — fixed

**The bug:** `classifier.py`'s `classify_extraction()` called `date_resolver.resolve_dates(extraction)` with no `reference_date`, which silently defaulted to `datetime.now()` inside `date_resolver.py`. This meant a relative date like "next Friday" or "in 2 weeks" resolved against whenever classification happened to run, not the reel's actual publish date — the gap grows the longer a reel sits in a processing queue before being classified.

**Root cause:** `combine.py`'s extraction output had no post-date field at all, so `classify_extraction` had nothing correct to pass even if it tried.

**The fix, across three files:**
- `url_downloader.py` now extracts the post's real publish date (`yt-dlp`'s `upload_date` for videos, `instaloader`'s `Post.date_utc` for photos), normalized to ISO 8601, and includes it in its returned dict as `post_date`.
- `combine.py` threads `post_date` through into its own output (`None` for local-file input, same as `caption_text`/`hashtags`, since there's no post to read it from).
- `date_resolver.py` gained `parse_post_date()`, and `classifier.py` now calls it and passes the result as `resolve_dates()`'s `reference_date`, instead of relying on the old (buggy) default.

**Covered by a regression test** (`tests/test_post_date_regression.py`) that posts a caption saying "next Friday" with a `post_date` set 10 days in the past, and asserts the resolved date is calculated relative to that post date, not today — this is exactly the scenario that was silently wrong before.

---

## `/api/process-link` integration choices — not locked

**Bare-name collision, fixed by renaming:** `backend/extraction/ocr/pipeline.py` originally bare-imported itself as `pipeline` (per the repo's flat sys.path.insert convention), colliding with `backend/pipeline`, the API's own proper package, also occupying the bare name `pipeline` in `sys.modules` once both are imported into the same process. Fixed by renaming the OCR module to `ocr_pipeline.py` (and its test to `test_ocr_pipeline.py`) rather than papering over it with a `sys.modules` stash/restore — the rename is permanent and needs no runtime workaround.

**Deferred (lazy) import of `combine.py`:** `run_extraction` is only actually imported on the first real `/api/process-link` request, not at module load. This lets the API start and its test suite run without extraction's heavy dependencies (Tesseract, FFmpeg, PyTorch/Whisper, yt-dlp, instaloader) installed — those are listed in `backend/api/requirements.txt` but were not installed or exercised end-to-end in this session; tests monkeypatch `app.run_extraction` / `app.classify_extraction` instead.

**`deadline_confidence` defaults to yellow:** `actions/engine.py::accept_opportunity()` only creates a calendar event when `deadline_confidence == "green"`. Link-ingested opportunities get this from the classifier; caption/upload-path opportunities (heuristic-only, no classifier involved) have no such field and so default to yellow — note-only on accept, never an unconfirmed date landing on the calendar. Revisit if caption/upload input should also get classifier-backed date confidence.

**Google auth is refresh-token-only:** no in-app OAuth consent flow; a refresh token is generated once via the OAuth Playground and passed through `GOOGLE_REFRESH_TOKEN`. Matches the rest of the repo's provider style (raw `urllib`, no SDK — see `backend/memory/providers.py`, `backend/pipeline/providers.py`) but means token issuance is a manual, external step, not something the app does for the user.
