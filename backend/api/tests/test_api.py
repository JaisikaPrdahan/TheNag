import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import app as app_module
from app import app


client = TestClient(app)


def _fake_extraction():
    return {
        "media_type": "video",
        "caption_text": "React developer hiring, remote role, apply by 12 October",
        "hashtags": ["#hiring"],
        "post_date": "2026-09-01T00:00:00",
        "ocr_results": [],
        "transcript": {"text": ""},
        "source_languages": [],
    }


def test_bootstrap_has_meaningful_seed_data():
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    body = response.json()
    assert len(body["opportunities"]) >= 25
    assert body["reflect"]["insights"]
    assert any(item["duplicate"]["status"] == "updated" for item in body["opportunities"])


def test_hindi_caption_is_processed_and_ranked():
    response = client.post("/api/process-caption", json={
        "caption": "React developer की भर्ती, remote काम, 2 years experience, apply by 12 October",
        "source_creator": "careergrid",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Jobs & Gigs"
    assert body["language"] == "Hindi / Hinglish"
    assert isinstance(body["rank"], int)
    assert body["why"]


def test_link_ingest_uses_classifier_category_and_dates(monkeypatch):
    monkeypatch.setattr(app_module, "run_extraction", lambda url: _fake_extraction())
    monkeypatch.setattr(app_module, "classify_extraction", lambda extraction: SimpleNamespace(
        primary_category="Jobs & Gigs",
        overall_confidence="green",
        resolved_dates=[{
            "date": "2026-10-12", "date_type": "application_deadline",
            "confidence": "yellow", "raw_text": "12 October", "source": "caption",
        }],
    ))
    before = len(app_module.opportunities)
    response = client.post("/api/process-link", json={
        "url": "https://www.instagram.com/reel/SOME_ID/", "source_creator": "careergrid",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Jobs & Gigs"
    assert body["category_confidence"] == "green"
    assert body["deadline"] == "2026-10-12"
    assert body["deadline_confidence"] == "yellow"
    assert isinstance(body["rank"], int)
    assert body["why"]
    assert body["duplicate"]["status"] in {"new", "updated", "exact", "similar_source"}
    assert body["recalled_memories"] is not None
    assert len(app_module.opportunities) == before + 1


def test_link_ingest_auto_fetch_failure_returns_typed_error(monkeypatch):
    def _raise(url):
        raise app_module.LinkFetchFailed("Instagram blocked the auto-fetch")

    monkeypatch.setattr(app_module, "run_extraction", _raise)
    response = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/BAD/"})
    assert response.status_code == 422
    assert response.json()["detail"]["error_type"] == "AutoFetchFailed"


def test_action_updates_private_memory_with_redaction():
    response = client.post("/api/opportunities/opp-01/action", json={
        "action": "rejected", "reason": "Contact me at person@example.com or 9876543210",
    })
    assert response.status_code == 200
    redactions = response.json()["memory_redactions"]
    assert {item["type"] for item in redactions} == {"email", "phone"}
