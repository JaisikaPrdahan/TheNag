"""
Transcribes spoken audio from a reel using Whisper. Whisper can pull
audio directly from a video file via FFmpeg internally, so there's no
separate audio-extraction step needed before this runs.

Requires FFmpeg installed on the system (not just a Python package) —
see the audio README for setup instructions.
"""

import whisper

# Maps our language names to Whisper's language codes.
# Whisper uses standard ISO 639-1 codes for most languages.
LANGUAGE_CODE_MAP = {
    "hindi": "hi",
    "english": "en",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    # Phase 2/3 languages — not validated yet, per docs/spec.md phased rollout.
    "marathi": "mr",
    "gujarati": "gu",
    "kannada": "kn",
    "malayalam": "ml",
    "odia": "or",
    "urdu": "ur",
}

PHASE_1_LANGUAGES = ["hindi", "english", "bengali", "tamil", "telugu"]

# Whisper model sizes, smallest/fastest to largest/most accurate:
# tiny, base, small, medium, large.
#
# LOCKED as "medium" based on real testing, not a guess: "small" produced
# fluent-sounding but hallucinated garbage (mixed Chinese/German-looking
# fragments) on real reel audio with background music, while "medium"
# produced a coherent, grammatically correct transcript on the exact
# same audio. This matters because background music mixed with talking
# is common in this content, not an edge case.
#
# Still unverified: whether "medium"'s output is actually *correct*
# (a native speaker needs to check it), only that it's structurally
# coherent where "small" wasn't. "medium" is also slower and needs more
# memory/disk (~1.4GB model download) — worth knowing if this becomes
# a real constraint on a low-resource machine.
DEFAULT_MODEL_SIZE = "medium"

_loaded_model = None


def _get_model(model_size=DEFAULT_MODEL_SIZE):
    """
    Loads the Whisper model once and reuses it, since loading is slow
    (the model has to be downloaded on first use, then loaded into
    memory every time otherwise).
    """
    global _loaded_model
    if _loaded_model is None:
        _loaded_model = whisper.load_model(model_size)
    return _loaded_model


def get_whisper_language_code(language_name):
    """
    Converts one of our language names (e.g. "hindi") into the code
    Whisper expects (e.g. "hi"). Returns None if the language name isn't
    recognized, or if None was passed in — both cases mean "let Whisper
    auto-detect the language instead of forcing one."
    """
    if not language_name:
        return None
    return LANGUAGE_CODE_MAP.get(language_name)


def transcribe_audio(media_path, language=None, model_size=DEFAULT_MODEL_SIZE):
    """
    Transcribes spoken audio from a video file.

    language: one of our language names (e.g. "hindi"), or None to let
    Whisper auto-detect the language itself. Auto-detection is
    reasonable to try first since we don't always know a reel's
    language in advance — but confirm with real testing whether
    specifying a language improves accuracy for this content, since
    auto-detect can guess wrong on code-switched (mixed-language) audio.

    Returns: {
        "text": str,               -- the full transcript
        "detected_language": str,  -- Whisper's own language guess
        "segments": [              -- per-segment breakdown with timestamps
            {"text": str, "start": float, "end": float}
        ]
    }
    """
    model = _get_model(model_size)

    whisper_lang_code = get_whisper_language_code(language)

    result = model.transcribe(media_path, language=whisper_lang_code)

    segments = [
        {
            "text": seg["text"].strip(),
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
        }
        for seg in result.get("segments", [])
    ]

    return {
        "text": result["text"].strip(),
        "detected_language": result.get("language"),
        "segments": segments,
    }


if __name__ == "__main__":
    # Quick manual test — pass a local video file OR a public Instagram
    # post URL (reel or photo) and it'll download it first, reusing the
    # same downloader the OCR subsystem uses.
    # Usage: python transcription.py <path_or_url> [language_name]
    import sys
    import os

    # Reuse the OCR subsystem's URL downloader rather than duplicating it.
    # This assumes the standard folder layout: backend/extraction/audio/
    # and backend/extraction/ocr/ as sibling folders.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ocr"))
    from url_downloader import is_url, download_media_from_url, AutoFetchFailed

    if len(sys.argv) < 2:
        print("Usage: python transcription.py <path_to_video OR instagram_url> [language_name]")
        sys.exit(1)

    input_arg = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else None

    if is_url(input_arg):
        print(f"Downloading media from URL: {input_arg}")
        try:
            download_result = download_media_from_url(input_arg)
            media_path = download_result["path"]
            media_type = download_result["media_type"]
            print(f"Downloaded {media_type} to: {media_path}")
            print(f"Caption: {download_result['caption_text']}")
            print(f"Hashtags: {download_result['hashtags']}")
            if media_type == "image":
                print("This is a photo post with no audio — nothing to transcribe.")
                sys.exit(0)
        except AutoFetchFailed as e:
            print(f"\n⚠ {e}")
            sys.exit(1)
    else:
        media_path = input_arg

    print(f"Transcribing (language hint: {language or 'auto-detect'})...")
    result = transcribe_audio(media_path, language=language)

    print(f"\nDetected language: {result['detected_language']}")
    print(f"\nFull transcript:\n{result['text']}")
    print(f"\nSegments:")
    for seg in result["segments"]:
        print(f"[{seg['start']}s - {seg['end']}s] {seg['text']}")