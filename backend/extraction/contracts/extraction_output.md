# Extraction Output Contract (LOCKED)

This is the exact shape `run_extraction()` (in `backend/extraction/combine.py`) returns. Person 2 (Classification) should build against this shape.

```python
{
    "media_type": "video" | "image",

    "caption_text": str | None,   # None only for local-file input (no post to read a caption from)
    "hashtags": [str, ...],       # extracted from caption_text; empty list if none found or no caption available
    "source_creator": str | None,  # OPTIONAL extra: posting account (yt-dlp uploader_id/channel, instaloader owner_username); URL input only, absent in older cached reels.
    "post_date": str | None,      # ISO 8601, the post's own publish date. None only for local-file input.
                                    # Person 2 MUST use this as the reference point for relative-date
                                    # resolution ("next Friday", "in 2 weeks") -- see date_resolver.parse_post_date().

    "ocr_results": [
        {
            "text": str,
            "timestamp": float,          # 0.0 for images (no timeline)
            "confidence_level": "green" | "yellow",  # "red" results are dropped before this point, never appear here
            "raw_confidence": float,     # Tesseract's 0-100 score
        },
        ...
    ],

    "transcript": {
        "text": str,                     # full transcript
        "detected_language": str,        # Whisper's own language guess, e.g. "hi", "en", "bn"
        "segments": [
            {"text": str, "start": float, "end": float},
            ...
        ]
    } | None,   # None for image posts — no audio to transcribe

    "source_languages": [str, ...]   # currently only ever contains the transcript's detected language, if any
}
```

## Known gaps — real, not hidden

1. **`caption_text`, `hashtags`, and `post_date` are only available for URL input, not local files.** When a URL is given, `caption_text` comes from `yt-dlp`'s `description` field (video posts) or `instaloader`'s `Post.caption` (photo posts); `post_date` comes from `yt-dlp`'s `upload_date` or `instaloader`'s `Post.date_utc`. None of these are guaranteed to always be populated by the source platform. `hashtags` is parsed out of `caption_text` via `url_downloader.extract_hashtags()`. For local-file input (no post to read from), all three are always `None`/`[]` — there's no metadata source to pull from a bare video/image file.

2. **`ocr_results` never contains `"red"` confidence entries.** They're filtered out in the OCR pipeline itself (see `docs/engineering-decisions.md`) — don't write classification logic that expects to see and handle red-tagged OCR facts, they simply won't be in this list.

3. **No confidence score exists for `transcript`.** Whisper doesn't give a clean built-in confidence number the way Tesseract does. This is an open decision — noted in `backend/extraction/audio/README.md` — not yet resolved. Until it is, treat transcript text as unscored; don't assume it's automatically "green" confidence just because it's present.

4. **Whisper model size is locked to `"medium"`**, based on real testing (see `docs/engineering-decisions.md`) — `"small"` hallucinated fluent-sounding garbage on real reel audio with background music. `"medium"` produces structurally coherent output but has not been verified for actual correctness by a native speaker yet.

5. **Music/song content produces empty transcripts.** Confirmed via real testing — Whisper is built for speech, not sung vocals, and returns nothing for music-video-style content. This is expected behavior for that content type, not a bug, and is unlikely to matter for TheNag's actual target content (announcements, not music).

## What Person 2 can rely on right now

- `ocr_results` and `transcript.segments` are real, tested outputs from real reel content
- Every OCR result present has already passed the red-confidence filter
- `caption_text`, `hashtags`, and `post_date` are real when input came from a URL — treat them as unreliable/empty for local-file input
- `transcript.text` may be empty (music content) or may contain hallucination artifacts from harder audio — don't assume every transcript is clean
- `media_type` reliably distinguishes video vs. image, driving whether `transcript` is populated at all
- **`post_date` must be used for relative-date resolution.** Calling `resolve_dates()` without it (or without first running it through `date_resolver.parse_post_date()`) silently falls back to the current time, which is wrong for any reel processed after the day it was posted — this was a real bug, now fixed (see `docs/engineering-decisions.md`).