"""Focused tests for demo cache and transcript-timeout behavior."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import combine


def test_cached_url_returns_saved_extraction_without_download(tmp_path, monkeypatch):
    url = "https://www.instagram.com/reels/DbfsdUnvDqM/?igsh=tracking"
    cached = {
        "media_type": "video", "caption_text": "Cached React role", "hashtags": ["jobs"],
        "post_date": "2026-09-01", "ocr_results": [], "transcript": None,
        "source_languages": [],
    }
    combine._save_cached_reel(url, cached, tmp_path)
    monkeypatch.setattr(combine, "download_media_from_url", lambda _: (_ for _ in ()).throw(AssertionError("download should not run")))

    assert combine.run_extraction("https://www.instagram.com/reels/DbfsdUnvDqM/", cache_dir=tmp_path) == cached


def test_timeout_result_keeps_caption_and_ocr_without_transcript(tmp_path, monkeypatch):
    monkeypatch.setattr(combine, "download_media_from_url", lambda _: {
        "path": "demo.mp4", "media_type": "video", "caption_text": "Caption survives", "hashtags": ["jobs"], "post_date": "2026-09-01",
    })
    monkeypatch.setattr(combine, "run_ocr_pipeline", lambda *args, **kwargs: [{"text": "OCR survives"}])
    monkeypatch.setattr(combine, "transcribe_audio", lambda *args, **kwargs: None)

    result = combine.run_extraction("https://www.instagram.com/reels/TIMEOUT/", cache_dir=tmp_path)

    assert result["caption_text"] == "Caption survives"
    assert result["ocr_results"] == [{"text": "OCR survives"}]
    assert result["transcript"] is None
