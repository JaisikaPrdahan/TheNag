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