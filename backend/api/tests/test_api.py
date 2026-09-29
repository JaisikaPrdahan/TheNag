import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import app as app_module
from app import app


client = TestClient(app)


def _fake_extraction(caption="React developer hiring, remote role, apply by 12 October"):
    return {
        "media_type": "video",
        "caption_text": caption,
        "hashtags": ["#hiring"],
        "post_date": "2026-09-01T00:00:00",
        "ocr_results": [],
        "transcript": {"text": ""},
        "source_languages": [],
    }


def _classification(category, confidence, resolved_dates=None):
    return SimpleNamespace(primary_category=category, overall_confidence=confidence, resolved_dates=resolved_dates or [])


def _ingest_link(monkeypatch, caption, category, confidence, resolved_dates, source_creator="careergrid"):
    monkeypatch.setattr(app_module, "run_extraction", lambda url: _fake_extraction(caption))
    monkeypatch.setattr(app_module, "classify_extraction", lambda extraction: _classification(category, confidence, resolved_dates))
    response = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/X/", "source_creator": source_creator})
    assert response.status_code == 200
    return response.json()


class _FakeMemoryProvider:
    def __init__(self, recall_result=None, reflect_result=None, raise_on_recall=False):
        self.recall_result = recall_result or []
        self.reflect_result = reflect_result
        self.raise_on_recall = raise_on_recall
        self.remembered = []

    def recall(self, user_id, query):
        if self.raise_on_recall:
            raise RuntimeError("Hindsight Cloud unreachable")
        return self.recall_result

    def remember(self, user_id, text, metadata):
        self.remembered.append((user_id, text, metadata))
        return {"redactions": []}

    def reflect(self, user_id):
        return self.reflect_result


class _FakeSourceTrustProvider:
    def __init__(self, recall_result=None):
        self.recall_result = recall_result or []
        self.remembered = []

    def recall(self, source_creator):
        return self.recall_result

    def remember(self, source_creator, text, metadata):
        self.remembered.append((source_creator, text, metadata))
        return {}


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


def test_caption_explicit_date_gets_real_classifier_confidence():
    response = client.post("/api/process-caption", json={
        "caption": "Frontend Developer hiring at Realdate Labs, remote role, apply by 12 October",
        "source_creator": "careergrid",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["deadline"] == "2026-10-12"
    assert body["deadline_confidence"] == "green"
    assert body["resolved_dates"]


def test_accept_green_date_creates_calendar_event_and_confirmed_note(monkeypatch):
    body = _ingest_link(monkeypatch, "Frontend Developer hiring at Greenleaf Technologies, remote role, apply by 12 October",
                         "Jobs & Gigs", "green",
                         [{"date": "2026-10-12", "date_type": "application_deadline", "confidence": "green", "raw_text": "12 October", "source": "caption"}])
    response = client.post(f"/api/opportunities/{body['id']}/action", json={"action": "accepted"})
    assert response.status_code == 200
    result = response.json()["action_result"]
    assert result["kind"] == "calendar_event"
    opportunity = next(o for o in app_module.opportunities if o["id"] == body["id"])
    assert opportunity["calendar_event_id"] == result["calendar_event_id"]
    assert opportunity["notion_page_id"] == result["notion_page_id"]
    assert opportunity["notes"]["status"] == "confirmed"


def test_accept_yellow_date_creates_note_only(monkeypatch):
    body = _ingest_link(monkeypatch, "Backend Engineer hiring at Yellowstone Systems, remote role, apply next Friday",
                         "Jobs & Gigs", "yellow",
                         [{"date": "2026-10-20", "date_type": "unknown", "confidence": "yellow", "raw_text": "next Friday", "source": "caption"}])
    response = client.post(f"/api/opportunities/{body['id']}/action", json={"action": "accepted"})
    result = response.json()["action_result"]
    assert result["kind"] == "note_only"
    assert result["status"] == "needs confirmation"
    opportunity = next(o for o in app_module.opportunities if o["id"] == body["id"])
    assert opportunity.get("calendar_event_id") is None
    assert opportunity["notion_page_id"] == result["notion_page_id"]


def test_accept_uncertain_category_creates_note_only(monkeypatch):
    body = _ingest_link(monkeypatch, "Random unrelated announcement about Mystery Ventures",
                         "Uncertain", "red", [])
    response = client.post(f"/api/opportunities/{body['id']}/action", json={"action": "accepted"})
    result = response.json()["action_result"]
    assert result["kind"] == "note_only"
    assert result["status"] == "uncertain category"
    opportunity = next(o for o in app_module.opportunities if o["id"] == body["id"])
    assert opportunity.get("calendar_event_id") is None


def test_accept_duplicate_of_accepted_opportunity_updates_existing(monkeypatch):
    caption = "Product Manager hiring at Dupliko Corp, remote role, apply by 20 November"
    resolved_dates = [{"date": "2026-11-20", "date_type": "application_deadline", "confidence": "green", "raw_text": "20 November", "source": "caption"}]
    first = _ingest_link(monkeypatch, caption, "Jobs & Gigs", "green", resolved_dates, source_creator="careergrid")
    first_accept = client.post(f"/api/opportunities/{first['id']}/action", json={"action": "accepted"}).json()["action_result"]

    second = _ingest_link(monkeypatch, caption, "Jobs & Gigs", "green", resolved_dates, source_creator="careergrid")
    assert second["duplicate"]["previous_id"] == first["id"]

    response = client.post(f"/api/opportunities/{second['id']}/action", json={"action": "accepted"})
    result = response.json()["action_result"]
    assert result["kind"] == "duplicate_update"
    assert result["calendar_event_id"] == first_accept["calendar_event_id"]

    updated_first = next(o for o in app_module.opportunities if o["id"] == first["id"])
    assert updated_first["notes"]["change_log"]
    second_opportunity = next(o for o in app_module.opportunities if o["id"] == second["id"])
    assert second_opportunity.get("calendar_event_id") is None


def test_action_updates_private_memory_with_redaction():
    response = client.post("/api/opportunities/opp-01/action", json={
        "action": "rejected", "reason": "Contact me at person@example.com or 9876543210",
    })
    assert response.status_code == 200
    redactions = response.json()["memory_redactions"]
    assert {item["type"] for item in redactions} == {"email", "phone"}


def test_duplicate_detected_via_recall_when_not_in_live_opportunities(monkeypatch):
    fake = _FakeMemoryProvider(recall_result=[{
        "text": "Viewed a role", "metadata": {
            "kind": "viewed", "opportunity_id": "ghost-opp", "title": "New opportunity", "company": "Recallco Labs",
        },
    }])
    monkeypatch.setattr(app_module, "memory_provider", fake)
    response = client.post("/api/process-caption", json={"caption": "Frontend Developer hiring at Recallco Labs, remote role"})
    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"]["status"] == "resurfaced"
    assert body["duplicate"]["previous_id"] == "ghost-opp"
    assert any(call[2].get("title") == body["title"] and call[2].get("company") == body["company"] for call in fake.remembered)


def test_source_trust_negative_facts_reduce_rank_and_show_in_why(monkeypatch):
    fake_trust = _FakeSourceTrustProvider(recall_result=[
        {"metadata": {"kind": "dead_link"}}, {"metadata": {"kind": "rejected_as_fake"}},
    ])
    monkeypatch.setattr(app_module, "source_trust_provider", fake_trust)
    response = client.post("/api/process-caption", json={
        "caption": "Backend Engineer hiring at Trustcheck Inc, remote role", "source_creator": "shadyacct",
    })
    assert response.status_code == 200
    body = response.json()
    assert any("dead or fake" in reason for reason in body["why"])


def test_accept_retains_a_source_trust_fact_with_redacted_reason(monkeypatch):
    fake_trust = _FakeSourceTrustProvider()
    monkeypatch.setattr(app_module, "source_trust_provider", fake_trust)
    response = client.post("/api/opportunities/opp-01/action", json={
        "action": "rejected", "reason": "this link is dead, email me at person@example.com",
    })
    assert response.status_code == 200
    assert fake_trust.remembered
    source_creator, text, metadata = fake_trust.remembered[-1]
    assert metadata["kind"] == "dead_link"
    assert "person@example.com" not in text


def test_reflect_uses_hindsight_when_it_returns_a_result(monkeypatch):
    fake = _FakeMemoryProvider(reflect_result={"period": "From Hindsight", "stats": {}, "insights": ["remote"], "skills": [], "nudge": ""})
    monkeypatch.setattr(app_module, "memory_provider", fake)
    response = client.get("/api/reflect")
    assert response.status_code == 200
    assert response.json()["period"] == "From Hindsight"


def test_reflect_falls_back_to_local_math_when_hindsight_has_nothing(monkeypatch):
    fake = _FakeMemoryProvider(reflect_result=None)
    monkeypatch.setattr(app_module, "memory_provider", fake)
    response = client.get("/api/reflect")
    assert response.status_code == 200
    assert response.json()["period"] == "Last 7 days"


def test_hindsight_failure_falls_back_and_logs_a_warning_not_silently(monkeypatch, caplog):
    fake = _FakeMemoryProvider(raise_on_recall=True)
    monkeypatch.setattr(app_module, "memory_provider", fake)
    with caplog.at_level("WARNING", logger="thenag.api"):
        response = client.post("/api/process-caption", json={"caption": "QA Engineer hiring at Warnco, remote role"})
    assert response.status_code == 200
    assert any("falling back" in record.message for record in caplog.records)
