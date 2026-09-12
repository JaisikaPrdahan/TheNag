"""
Runs Tesseract OCR on a single frame image, and converts its raw
confidence score into our green/yellow/red system from docs/spec.md
Section 4.

Requires the Tesseract binary to be installed on the machine (not just
this Python package) — see the OCR README for setup instructions.
"""

import pytesseract
from PIL import Image

from preprocess import preprocess_for_ocr

# Maps our language names to Tesseract's language codes.
# Full list of Tesseract codes: https://github.com/tesseract-ocr/tessdata
LANGUAGE_CODE_MAP = {
    "hindi": "hin",
    "english": "eng",
    "bengali": "ben",
    "tamil": "tam",
    "telugu": "tel",
    # Phase 2/3 languages — not validated yet, per docs/spec.md phased rollout.
    # Add these to PHASE_1_LANGUAGES only once someone has actually tested
    # OCR quality for them and it's good enough to trust.
    "marathi": "mar",
    "gujarati": "guj",
    "kannada": "kan",
    "malayalam": "mal",
    "odia": "ori",
    "urdu": "urd",
}

# Locked in docs/spec.md — these are the only languages we treat as
# "validated" for now. Everything else gets capped at yellow confidence
# even if Tesseract itself reports a high score, since we haven't proven
# it's actually reliable yet.
PHASE_1_LANGUAGES = ["hindi", "english", "bengali", "tamil", "telugu"]


def get_tesseract_lang_string(languages=None):
    """
    Build the '+'-joined language string Tesseract expects, e.g. "hin+eng".
    Kept as a standalone utility (used in tests, and potentially useful
    for logging) — run_ocr_on_frame itself no longer uses a combined
    string, see the note below.
    """
    if languages is None:
        languages = PHASE_1_LANGUAGES
    codes = [LANGUAGE_CODE_MAP[lang] for lang in languages if lang in LANGUAGE_CODE_MAP]
    return "+".join(codes) if codes else "eng"


def _run_tesseract_single_language(image, lang_string):
    """
    Runs Tesseract with the given language string (can be a single code
    like "eng" or a combined one like "hin+eng") and returns
    {"text", "confidence"}.
    """
    data = pytesseract.image_to_data(image, lang=lang_string, output_type=pytesseract.Output.DICT)

    words = []
    confidences = []
    for i, word in enumerate(data["text"]):
        conf_raw = data["conf"][i]
        conf = int(conf_raw) if str(conf_raw) not in ("-1", "") else None
        if word.strip() and conf is not None and conf >= 0:
            words.append(word)
            confidences.append(conf)

    text = " ".join(words)
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

    return {"text": text, "confidence": avg_confidence}


def run_ocr_on_frame(frame_path, languages=None, use_preprocessing=True):
    """
    Run OCR on a single frame image.

    IMPORTANT — reverted from an earlier version that ran each language
    separately and kept the best result. Real reel testing showed that
    approach actively hurts bilingual frames (e.g. a banner showing both
    "सड़क परिवहन एवं राजमार्ग मंत्रालय" and "MINISTRY OF ROAD TRANSPORT
    AND HIGHWAYS" in the same frame): running Hindi-only or English-only
    OCR on a genuinely bilingual frame means whichever script isn't being
    targeted just gets read as garbage, producing a worse result than a
    single combined-language call that can read both scripts correctly
    at once. Combined-language OCR is the right default given how common
    bilingual captions are in this content.

    use_preprocessing controls whether grayscale/contrast/binarization
    runs before OCR — kept as a toggle so preprocessing's actual effect
    can be tested in isolation rather than assumed.

    Returns: {"text": str, "confidence": float}
    "confidence" is Tesseract's average word-level confidence, 0-100.
    """
    lang_string = get_tesseract_lang_string(languages)

    if use_preprocessing:
        preprocessed = preprocess_for_ocr(frame_path)
        image = Image.fromarray(preprocessed)
    else:
        image = Image.open(frame_path)

    return _run_tesseract_single_language(image, lang_string)


def confidence_to_level(raw_confidence, script_is_validated=True):
    """
    Convert Tesseract's 0-100 confidence score into our green/yellow/red
    system, per docs/spec.md Section 4.

    Non-validated scripts (anything outside Phase 1) are capped at
    yellow even on a good raw score, because we haven't confirmed OCR
    quality is actually trustworthy for them yet — this matches the
    spec's rule that lower-confidence scripts default to yellow.
    """
    if not script_is_validated:
        return "yellow" if raw_confidence >= 50 else "red"

    if raw_confidence >= 75:
        return "green"
    elif raw_confidence >= 45:
        return "yellow"
    else:
        return "red"