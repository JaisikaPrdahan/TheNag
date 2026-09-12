# OCR Subsystem

Part of Person 1's Extraction subsystem. Turns a reel's video into a list of on-screen text segments, each with a timestamp and a confidence level.

## What this does

1. Pulls still frames out of the video, roughly one per second (`frame_extraction.py`)
2. Runs Tesseract OCR on each frame (`ocr_engine.py`)
3. Scores each result's confidence and collapses duplicate consecutive text (`pipeline.py`)
4. Returns a list like:
```python
[
  {"text": "Apply by Nov 15", "timestamp": 3.0, "confidence_level": "green", "raw_confidence": 82.4},
  {"text": "Team size: 2-4", "timestamp": 7.0, "confidence_level": "yellow", "raw_confidence": 58.1}
]
```
This is what feeds into the shared extraction output object (see `backend/extraction/contracts/`).

## One-time setup (system-level, do this before installing Python packages)

Tesseract itself is a separate program, not just a Python package.

**Windows:**
1. Download the installer from https://github.com/UB-Mannheim/tesseract/wiki
2. During install, check the box for additional language packs — you need Hindi, Bengali, Tamil, Telugu (English is included by default)
3. Add the install folder (usually `C:\Program Files\Tesseract-OCR`) to your system PATH
4. Open a **new** terminal and verify: `tesseract --version` should print a version number

**Mac:** `brew install tesseract tesseract-lang`

**Linux:** `sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-ben tesseract-ocr-tam tesseract-ocr-tel`

## Python setup

From this folder:
```
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac/Linux)
pip install -r requirements.txt
```

## Testing

**Automated tests (no video needed):**
```
python -m pytest tests/test_ocr_engine.py
```

**Manual test against a real reel:**
```
python pipeline.py path\to\a\reel.mp4
```
This prints every distinct text segment found, with its timestamp and confidence. Try this on a few different real reels early — in different languages — to see how OCR quality actually varies before building anything more on top of it.

## Known limitations (expected, not bugs)

- OCR quality is expected to be strongest for Hindi and English, weaker for the other Phase 1 scripts — that's why the confidence system exists, not something to "fix" by tweaking thresholds until it looks better on one sample.
- Stylized fonts, fast-moving text, and low-resolution reels will produce garbage or empty results sometimes — this should show up as a low confidence score or missing text, not a crash.
- Phase 2/3 languages (Marathi, Gujarati, Kannada, Malayalam, Odia, Urdu) aren't in `PHASE_1_LANGUAGES` yet — don't add them to that list until someone has actually tested OCR quality for them and confirmed it's usable.