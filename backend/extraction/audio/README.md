# Audio Transcription Subsystem

Part of Person 1's Extraction subsystem. Turns a reel's spoken audio into text, using Whisper.

## What this does

Takes a video file, runs it through Whisper (which internally uses FFmpeg to pull the audio track), and returns:
- The full transcript
- Whisper's own guess at what language it detected
- A per-segment breakdown with timestamps

This feeds into the shared extraction output object alongside OCR results (see `backend/extraction/contracts/`).

## One-time setup

**FFmpeg must be installed on the system** (not just a Python package) — Whisper calls it internally to extract audio from video.

Check if you have it:
```
ffmpeg -version
```

If not installed (Windows): download from https://www.gyan.dev/ffmpeg/builds/ (the "release essentials" build), extract it somewhere permanent, and add its `bin` folder to your system PATH. Open a **new** terminal afterward and re-check `ffmpeg -version`.

## Python setup

From this folder:
```
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate     (Mac/Linux)
pip install -r requirements.txt
```

**Note:** Whisper pulls in PyTorch as a dependency, which is a large download (several hundred MB) and can take a few minutes to install.

## Testing

**Manual test against a real local file:**
```
python transcription.py path\to\a\reel.mp4
```
This auto-detects the language. To hint a specific language instead:
```
python transcription.py path\to\a\reel.mp4 hindi
```

**Manual test against a public Instagram URL** (reel or photo post — reuses the OCR subsystem's downloader, so this only works if `backend/extraction/ocr/url_downloader.py` exists as a sibling folder):
```
python transcription.py "https://www.instagram.com/reel/SOME_ID/"
python transcription.py "https://www.instagram.com/reel/SOME_ID/" hindi
```
If you pass a photo post URL (no audio), it'll download it, notice there's nothing to transcribe, and exit cleanly rather than erroring.

Try this on real reels early, in different languages and via both local files and URLs, to see how transcription quality actually varies — same approach as the OCR subsystem. Don't assume it works well until you've seen real output.

## Known things to test and decide, not yet settled

- **Model size:** currently defaulting to Whisper's "small" model as a speed/accuracy balance. Larger models ("medium", "large") are more accurate but slower — worth comparing against real reel audio before locking this in.
- **Auto-detect vs. specifying language:** auto-detection is the current default, but code-switched (mixed Hindi-English) audio might confuse it. Worth testing both approaches against real samples, same as we discovered combined-language OCR worked better than per-language for bilingual text.
- **Confidence scoring:** unlike the OCR subsystem, this doesn't yet produce a confidence score per segment. Whisper doesn't give a clean built-in confidence number the way Tesseract does — this needs a follow-up decision on how to determine confidence for the spec's green/yellow/red system (e.g., using Whisper's internal log-probability output, or comparing detected language against expected language as a proxy signal).

## Known limitations (expected, not bugs)

- Transcription quality is expected to vary across languages — same phased-rollout logic as OCR applies (Phase 1: Hindi, English, Bengali, Tamil, Telugu).
- Background music, overlapping speech, or very short/quiet audio clips will produce poor or empty transcripts — this is expected, not something to "fix" by tweaking settings until one sample looks better.