"""
Combines OCR and audio transcription into one unified extraction
output — this is the actual integration point for Person 1's two
subsystems, which until now only existed as separate, independently
testable pipelines. This is what Person 2 (Classification) should
actually call.

Caption text, hashtags, and post_date (per docs/spec.md Section 1/2)
are pulled from the source post when a URL is given — see
url_downloader.py. Local file input has no post metadata to pull from,
so caption_text, hashtags, and post_date are always empty/None in that
case (there's no post to read a caption or publish date off of, just a
bare media file). post_date matters specifically because Person 2's
relative-date resolution ("next Friday", "in 2 weeks") must be
calculated against the reel's own publish date, not whenever
classification happens to run.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ocr"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "audio"))

from url_downloader import is_url, download_media_from_url, AutoFetchFailed  # noqa: E402
from pipeline import run_ocr_pipeline  # noqa: E402
from transcription import transcribe_audio  # noqa: E402


def run_extraction(media_path_or_url, temp_frame_dir="./_temp_frames", languages=None):
    """
    Runs the full extraction pipeline on a single reel/post: downloads
    it if given a URL, runs OCR (video and image both), runs Whisper
    transcription (video only, since images have no audio), and
    returns one combined object matching the extraction contract (see
    backend/extraction/contracts/extraction_output.md).

    Raises AutoFetchFailed if a URL is given and auto-fetch doesn't
    work — the caller should catch this and fall back to asking the
    user to upload the file manually, per docs/spec.md Section 8.
    """
    if is_url(media_path_or_url):
        download_result = download_media_from_url(media_path_or_url)
        media_path = download_result["path"]
        media_type = download_result["media_type"]
        caption_text = download_result["caption_text"]
        hashtags = download_result["hashtags"]
        post_date = download_result["post_date"]
    else:
        media_path = media_path_or_url
        media_type = "image" if media_path.lower().endswith((".jpg", ".jpeg", ".png")) else "video"
        caption_text = None  # no post to read a caption from — this is a bare local file
        hashtags = []
        post_date = None      # no post to read a publish date from either

    ocr_results = run_ocr_pipeline(
        media_path,
        temp_frame_dir=temp_frame_dir,
        languages=languages,
        media_type=media_type,
    )

    transcript = None
    if media_type == "video":
        transcript = transcribe_audio(media_path, language=None)

    source_languages = set()
    if transcript and transcript.get("detected_language"):
        source_languages.add(transcript["detected_language"])

    return {
        "media_type": media_type,
        "caption_text": caption_text,
        "hashtags": hashtags,
        "post_date": post_date,
        "ocr_results": ocr_results,
        "transcript": transcript,
        "source_languages": list(source_languages),
    }


if __name__ == "__main__":
    # Quick manual test — pass a local video/image file OR a public
    # Instagram post URL (reel or photo).
    # Usage: python combine.py <path_or_url>
    import sys as _sys

    if len(_sys.argv) < 2:
        print("Usage: python combine.py <path_to_video_or_image OR instagram_url>")
        _sys.exit(1)

    input_arg = _sys.argv[1]

    try:
        result = run_extraction(input_arg)
    except AutoFetchFailed as e:
        print(f"\n⚠ {e}")
        _sys.exit(1)

    print(f"\nMedia type: {result['media_type']}")
    print(f"Caption text: {result['caption_text']}")
    print(f"Hashtags: {result['hashtags']}")
    print(f"Post date: {result['post_date']}")

    print(f"\nOCR results ({len(result['ocr_results'])} segments):")
    for r in result["ocr_results"]:
        print(f"  [{r['timestamp']}s] ({r['confidence_level']}, {r['raw_confidence']:.1f}%) {r['text']}")

    if result["transcript"]:
        print(f"\nTranscript (detected language: {result['transcript']['detected_language']}):")
        print(f"  {result['transcript']['text']}")
    else:
        print("\nNo transcript (image post — no audio to transcribe)")

    print(f"\nSource languages detected: {result['source_languages']}")