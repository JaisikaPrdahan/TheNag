"""
Transcribes spoken audio from a reel using Whisper. Whisper can pull
audio directly from a video file via FFmpeg internally, so there's no
separate audio-extraction step needed before this runs.

Requires FFmpeg installed on the system (not just a Python package) —
see the audio README for setup instructions.
"""

import json
import logging
import mimetypes
import multiprocessing
import os
import queue
import uuid
from urllib import error, request

logger = logging.getLogger("thenag.transcription")

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
# The prior medium-model decision remains recorded in
# docs/engineering-decisions.md. The demo must have a bounded CPU fallback,
# so the local path now deliberately uses the smaller model and is terminated
# after 60 seconds. Hosted Groq transcription is preferred when configured.
DEFAULT_MODEL_SIZE = "small"
LOCAL_TRANSCRIPTION_TIMEOUT_SECONDS = 60
GROQ_TRANSCRIPTION_TIMEOUT_SECONDS = 60
# Groq sits behind Cloudflare, which 403s urllib's default User-Agent.
GROQ_HEADERS = {"User-Agent": "TheNag/1.0", "Accept": "application/json"}
GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_TRANSCRIPTION_MODEL = "whisper-large-v3-turbo"

_loaded_model = None


def _get_model(model_size=DEFAULT_MODEL_SIZE):
    """
    Loads the Whisper model once and reuses it, since loading is slow
    (the model has to be downloaded on first use, then loaded into
    memory every time otherwise).
    """
    global _loaded_model
    if _loaded_model is None:
        # Keep unit tests and caption/OCR-only paths usable without installing
        # the very large local Whisper/PyTorch dependency.
        import whisper
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


def _normalise_result(result):
    """Maps both local Whisper and Groq response shapes to our contract."""
    segments = [
        {
            "text": segment["text"].strip(),
            "start": round(segment["start"], 2),
            "end": round(segment["end"], 2),
        }
        for segment in result.get("segments", [])
    ]
    return {
        "text": result.get("text", "").strip(),
        "detected_language": result.get("language"),
        "segments": segments,
    }


def _transcribe_local(media_path, language, model_size):
    model = _get_model(model_size)
    result = model.transcribe(media_path, language=get_whisper_language_code(language))
    return _normalise_result(result)


def _local_transcription_worker(result_queue, media_path, language, model_size):
    """Runs in a child process so a CPU-bound model can be terminated."""
    try:
        result_queue.put(("ok", _transcribe_local(media_path, language, model_size)))
    except Exception as exc:  # pragma: no cover - surfaced in parent process
        result_queue.put(("error", str(exc)))


def _multipart_transcription_body(media_path, language):
    boundary = f"----TheNag{uuid.uuid4().hex}"
    pieces = []

    def add_field(name, value):
        pieces.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(), b"\r\n",
        ])

    add_field("model", os.getenv("GROQ_WHISPER_MODEL", GROQ_TRANSCRIPTION_MODEL))
    add_field("response_format", "json")
    language_code = get_whisper_language_code(language)
    if language_code:
        add_field("language", language_code)

    filename = os.path.basename(media_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(media_path, "rb") as media_file:
        media = media_file.read()
    pieces.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(), media, b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return boundary, b"".join(pieces)


def _transcribe_with_groq(media_path, language):
    boundary, body = _multipart_transcription_body(media_path, language)
    response = request.Request(
        os.getenv("GROQ_TRANSCRIPTION_URL", GROQ_TRANSCRIPTION_URL),
        data=body,
        headers={
            **GROQ_HEADERS,
            "Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(response, timeout=GROQ_TRANSCRIPTION_TIMEOUT_SECONDS) as http_response:
            return _normalise_result(json.loads(http_response.read().decode("utf-8")))
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", "replace")[:500]
        logger.warning("Groq transcription HTTP %s: %s", exc.code, body_text)
        raise RuntimeError(f"Groq transcription failed: HTTP {exc.code}: {body_text}") from exc


def _transcribe_locally_with_timeout(media_path, language, model_size, timeout_seconds):
    result_queue = multiprocessing.Queue()
    worker = multiprocessing.Process(
        target=_local_transcription_worker,
        args=(result_queue, media_path, language, model_size),
        daemon=True,
    )
    worker.start()
    worker.join(timeout_seconds)
    if worker.is_alive():
        worker.terminate()
        worker.join()
        return None
    try:
        status, payload = result_queue.get(timeout=2)
    except queue.Empty:
        return None
    if status == "error":
        raise RuntimeError(f"Local Whisper transcription failed: {payload}")
    return payload


def transcribe_audio(media_path, language=None, model_size=DEFAULT_MODEL_SIZE,
                     timeout_seconds=LOCAL_TRANSCRIPTION_TIMEOUT_SECONDS):
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
    if os.getenv("GROQ_API_KEY"):
        try:
            return _transcribe_with_groq(media_path, language)
        except Exception as exc:
            logger.warning("Groq transcription failed (%s); falling back to local Whisper %r", exc, DEFAULT_MODEL_SIZE)
            model_size = DEFAULT_MODEL_SIZE
    return _transcribe_locally_with_timeout(media_path, language, model_size, timeout_seconds)


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
