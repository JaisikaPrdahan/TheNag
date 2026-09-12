# Extraction — Combined Pipeline

This is the integration point for Person 1's two subsystems (`ocr/` and `audio/`). It's what Person 2 (Classification) should actually call, not the subsystems individually.

## What this does

`combine.py`'s `run_extraction()` takes a local file path or an Instagram URL, and returns one object containing:
- The post's caption text and hashtags (URL input only — see `contracts/extraction_output.md`)
- OCR results from the video/image
- A Whisper transcript (video only)

See `contracts/extraction_output.md` for the exact locked output shape and known gaps.

## Why this needs its own venv

`combine.py` imports from both `ocr/` and `audio/`, so it needs **both** subsystems' dependencies installed at once. Neither subsystem's own venv has both sets of packages — this folder has its own dedicated venv and `requirements.txt` covering everything.

## Setup

```
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac/Linux)
pip install -r requirements.txt
```

You'll also need Tesseract and FFmpeg installed at the system level — see `ocr/README.md` and `audio/README.md` for those setup steps, since this folder relies on both.

## Testing

**Local file:**
```
python combine.py path\to\a\reel.mp4
```

**Instagram URL** (reel or photo post):
```
python combine.py "https://www.instagram.com/reel/SOME_ID/"
```

Confirmed working end-to-end against real Instagram content — see `docs/engineering-decisions.md` for what was tested and found.