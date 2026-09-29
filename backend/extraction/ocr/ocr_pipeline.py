"""
The full OCR pipeline: takes a reel's video file, extracts frames, runs
OCR on each one, and returns the ocr_text results in the shape the
extraction contract expects (see backend/extraction/contracts/).
"""

from frame_extraction import extract_frames
from ocr_engine import run_ocr_on_frame, confidence_to_level, PHASE_1_LANGUAGES

# Consecutive results whose text overlaps by at least this ratio (of
# shared words, relative to the smaller reading's word count) are
# treated as the same on-screen text, not two distinct segments.
NEAR_DUPLICATE_SIMILARITY_THRESHOLD = 0.6


def run_ocr_pipeline(media_path, temp_frame_dir, languages=None, use_preprocessing=False, media_type="video"):
    """
    Runs the full pipeline: (video: extract frames -> OCR each frame)
    or (image: OCR the single image directly) -> tag confidence -> drop
    untrustworthy results -> collapse near-duplicates (video only —
    there's nothing to dedupe with a single image).

    media_type: "video" (default) treats media_path as a video file and
    runs frame extraction. "image" treats it as a single static image
    (e.g. an Instagram photo post) and runs OCR on it directly, with
    timestamp fixed at 0.0 since there's no timeline to place it on.

    use_preprocessing defaults to False based on real reel testing: the
    grayscale/CLAHE/adaptive-threshold preprocessing in preprocess.py
    was expected to help, but on actual reel footage it introduced more
    noise than it removed — likely because adaptive thresholding reacts
    to JPEG compression artifacts and photographic backgrounds as if
    they were text, producing garbled extra characters and *lower*
    confidence than running OCR on the raw frame. The toggle is kept in
    case it helps on different footage (e.g. reels with a flat solid
    background behind the caption), but don't assume it helps without
    testing against real samples first.

    Returns: list of dicts, each shaped like:
        {"text": str, "timestamp": float, "confidence_level": str, "raw_confidence": float}
    Frames/images with no readable text, or with red-confidence
    (untrustworthy) text, are dropped entirely rather than passed
    forward — a red-tagged result has no value to Person 2's classifier
    even with the warning label, so there's no reason to keep it.
    """
    if languages is None:
        languages = PHASE_1_LANGUAGES

    script_is_validated = set(languages).issubset(set(PHASE_1_LANGUAGES))

    if media_type == "image":
        ocr_result = run_ocr_on_frame(media_path, languages, use_preprocessing=use_preprocessing)

        if not ocr_result["text"].strip():
            return []  # nothing readable in the image at all

        confidence_level = confidence_to_level(ocr_result["confidence"], script_is_validated)

        if confidence_level == "red":
            return []  # untrustworthy — same rule as for video frames

        return [{
            "text": ocr_result["text"],
            "timestamp": 0.0,
            "raw_confidence": ocr_result["confidence"],
            "confidence_level": confidence_level,
        }]

    # media_type == "video" — the original frame-by-frame path
    frames = extract_frames(media_path, temp_frame_dir)
    results = []

    for frame_path, timestamp in frames:
        ocr_result = run_ocr_on_frame(frame_path, languages, use_preprocessing=use_preprocessing)

        if not ocr_result["text"].strip():
            continue  # nothing readable on this frame, skip it

        confidence_level = confidence_to_level(ocr_result["confidence"], script_is_validated)

        if confidence_level == "red":
            continue  # untrustworthy — drop it rather than pass it forward

        results.append({
            "text": ocr_result["text"],
            "timestamp": round(timestamp, 2),
            "raw_confidence": ocr_result["confidence"],
            "confidence_level": confidence_level,
        })

    return deduplicate_ocr_results(results)


def _text_similarity(a, b):
    """
    Word-overlap similarity between two strings, 0.0 to 1.0. Used to catch
    near-duplicate OCR reads of the same on-screen text across adjacent
    frames.

    Uses word-set overlap (how many words the two strings share, out of
    the smaller string's word count) rather than raw character-sequence
    similarity. This matters because real OCR noise often adds or drops
    extra garbled words around a stable core phrase — e.g. "MINISTRY OF
    ROAD TRANSPORT AND HIGHWAYS" vs "एवं राजमार्ग मंत्रालय MINISTRY OF ,
    ROAD TRANSPORT AND HIGHWAYS" are clearly the same underlying text,
    but a character-sequence comparison scores them as dissimilar once
    one reading has much more surrounding noise than the other.
    """
    words_a = set(a.strip().lower().split())
    words_b = set(b.strip().lower().split())

    if not words_a or not words_b:
        return 0.0

    overlap = words_a & words_b
    smaller_set_size = min(len(words_a), len(words_b))

    return len(overlap) / smaller_set_size


def deduplicate_ocr_results(results):
    """
    Reels typically show the same on-screen text across many consecutive
    frames (since text usually stays on screen for a couple of seconds),
    and OCR often reads each occurrence slightly differently due to noise
    — so exact-match deduplication alone isn't enough (real reel testing
    showed the same sentence appearing 10 times with minor variations).

    This collapses consecutive near-duplicate text into a single entry:
    when two consecutive results are similar enough, only the
    higher-confidence one is kept, at whichever timestamp it occurred.
    """
    if not results:
        return []

    deduped = [results[0]]
    for current in results[1:]:
        previous = deduped[-1]
        similarity = _text_similarity(current["text"], previous["text"])

        if similarity >= NEAR_DUPLICATE_SIMILARITY_THRESHOLD:
            # Same underlying text — keep whichever reading has higher
            # confidence, since that's more likely to be accurate.
            if current["raw_confidence"] > previous["raw_confidence"]:
                deduped[-1] = current
            continue

        deduped.append(current)

    return deduped


if __name__ == "__main__":
    # Quick manual test — pass a local video/image file OR a public
    # Instagram post URL (reel or photo) and it'll download it first,
    # automatically detecting whether it's a video or a photo.
    # Usage: python ocr_pipeline.py <path_or_url> [--preprocess]
    import sys
    from url_downloader import is_url, download_media_from_url, AutoFetchFailed

    if len(sys.argv) < 2:
        print("Usage: python ocr_pipeline.py <path_to_video_or_image OR instagram_url> [--preprocess]")
        sys.exit(1)

    input_arg = sys.argv[1]
    use_preprocessing = "--preprocess" in sys.argv

    if is_url(input_arg):
        print(f"Downloading media from URL: {input_arg}")
        try:
            download_result = download_media_from_url(input_arg)
            media_path = download_result["path"]
            media_type = download_result["media_type"]
            print(f"Downloaded {media_type} to: {media_path}")
            print(f"Caption: {download_result['caption_text']}")
            print(f"Hashtags: {download_result['hashtags']}")
        except AutoFetchFailed as e:
            # This is the graceful-fallback case: auto-fetch didn't work,
            # for whatever reason. In the real app, this is exactly where
            # the UI would prompt the user to upload the file directly
            # instead of showing them a raw error.
            print(f"\n⚠ {e}")
            sys.exit(1)
    else:
        media_path = input_arg
        # Guess media type from file extension for local files.
        media_type = "image" if media_path.lower().endswith((".jpg", ".jpeg", ".png")) else "video"

    results = run_ocr_pipeline(
        media_path,
        temp_frame_dir="./_temp_frames",
        use_preprocessing=use_preprocessing,
        media_type=media_type,
    )

    print(f"\nMedia type: {media_type} | Preprocessing: {'ON' if use_preprocessing else 'OFF'}")
    print(f"Found {len(results)} distinct text segments:\n")
    for r in results:
        print(f"[{r['timestamp']}s] ({r['confidence_level']}, {r['raw_confidence']:.1f}%) {r['text']}")