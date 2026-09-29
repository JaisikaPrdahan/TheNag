import io
import json
import os
import sys

# app.py loads backend/.env without overriding real env vars, so blank every provider key first to keep tests offline.
for _key in ("GROQ_API_KEY", "HINDSIGHT_API_URL", "HINDSIGHT_API_KEY", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
             "GOOGLE_REFRESH_TOKEN", "NOTION_API_KEY", "NOTION_DATABASE_ID", "ENABLE_LOCAL_WHISPER"):
    os.environ[_key] = ""
import tempfile
os.environ["THENAG_STORE_PATH"] = os.path.join(tempfile.mkdtemp(), "store.json")  # never touch the real backend/data/store.json
os.environ["DEMO_SEED"] = "true"  # most tests here exercise the seeded demo feed; DEMO_SEED off is tested explicitly below
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
            "kind": "viewed", "opportunity_id": "ghost-opp", "title": "", "company": "Recallco Labs",
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
    fake = _FakeMemoryProvider(reflect_result={"text": "From Hindsight"})
    monkeypatch.setattr(app_module, "memory_provider", fake)
    response = client.get("/api/reflect")
    assert response.status_code == 200
    assert response.json()["insights"][0] == "From Hindsight"


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


def test_link_uses_groq_over_combined_caption_ocr_transcript(monkeypatch):
    seen = {}

    class FakeGroq:
        def extract(self, text):
            seen["text"] = text
            return {"title": "SIH Resource Lead", "company": "TechDoodles", "location": "unknown", "category": "Jobs & Gigs"}

    extraction = _fake_extraction("Caption words")
    extraction["ocr_results"] = [{"text": "OCR words"}]
    extraction["transcript"] = {"text": "Transcript words"}
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(app_module, "GroqOpportunityExtractor", FakeGroq)
    monkeypatch.setattr(app_module, "run_extraction", lambda url: extraction)
    monkeypatch.setattr(app_module, "classify_extraction", lambda e: _classification("Uncertain", "red"))
    body = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/G/"}).json()
    assert all(part in seen["text"] for part in ("Caption words", "OCR words", "Transcript words"))
    assert body["title"] == "SIH Resource Lead" and body["company"] == "TechDoodles"
    assert body["location"] == "Not provided"  # LLM placeholder "unknown" ignored, heuristic value kept
    assert body["category"] == "Uncertain" and body["category_confidence"] == "red"  # classifier wins


def test_link_without_confident_title_or_company_leaves_them_empty(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    caption = "Everyone wants to win SIH. Comment PPT and I'll send it. #Hackathon"
    body = _ingest_link(monkeypatch, caption, "Uncertain", "red", [])
    assert body["title"] == "" and body["company"] == ""


def test_accept_returns_mock_confirmation_labels(monkeypatch):
    resolved = [{"date": "2026-11-20", "date_type": "application_deadline", "confidence": "green", "raw_text": "20 Nov", "source": "caption"}]
    item = _ingest_link(monkeypatch, "Analyst hiring at Confirmo Corp, apply by 20 November", "Jobs & Gigs", "green", resolved)
    body = client.post(f"/api/opportunities/{item['id']}/action", json={"action": "accepted"}).json()
    labels = [c["label"] for c in body["confirmation"]]
    assert any("Added to calendar (mock" in label for label in labels)
    assert any("Note saved (mock" in label for label in labels)
    assert all(c["mock"] and c["url"] is None for c in body["confirmation"])


def test_accept_confirmation_names_real_providers_with_links(monkeypatch):
    monkeypatch.setattr(app_module, "calendar_mode", "google-calendar")
    monkeypatch.setattr(app_module, "notes_mode", "notion")
    items = app_module._confirmation({"kind": "calendar_event", "calendar_event_id": "e1", "calendar_url": "https://cal/e1",
                                      "notion_page_id": "p1", "notion_url": "https://notion/p1"})
    assert [(c["label"], c["url"]) for c in items] == [("Added to Google Calendar", "https://cal/e1"), ("Notion page created", "https://notion/p1")]


def test_demo_seed_off_starts_empty_and_on_loads_seed(monkeypatch):
    off = app_module.load_state(False)
    assert off["opportunities"] == [] and off["sources"] == [] and off["memories"] == [] and off["actions"] == []
    assert app_module.load_state(True)["opportunities"]
    monkeypatch.setenv("DEMO_SEED", "false")
    assert app_module.DemoMemoryProvider().memories == []
    monkeypatch.setenv("DEMO_SEED", "true")
    assert app_module.DemoMemoryProvider().memories


def test_empty_state_bootstrap_and_confidence_label(monkeypatch):
    empty = app_module.load_state(False)
    monkeypatch.setattr(app_module, "seed", empty)
    monkeypatch.setattr(app_module, "opportunities", empty["opportunities"])
    monkeypatch.setattr(app_module, "sources", empty["sources"])
    monkeypatch.setattr(app_module, "source_by_name", {})
    monkeypatch.setattr(app_module, "memory_provider", _FakeMemoryProvider())
    monkeypatch.setattr(app_module, "_reflect", lambda user_id: {})
    body = client.get("/api/bootstrap").json()
    assert body["opportunities"] == [] and body["memories"] == []
    result = client.post("/api/process-caption", json={"caption": "Python developer hiring at Emptyco Ltd"}).json()
    assert result["personalized"] is False
    assert result["source_detail"]["observation_count"] == 0


def test_groq_403_does_not_break_link_pipeline(monkeypatch):
    from urllib import error
    from pipeline import providers

    def forbidden(*args, **kwargs):
        raise error.HTTPError("https://api.groq.com", 403, "Forbidden", {}, io.BytesIO(b'{"error":"blocked"}'))

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(providers.request, "urlopen", forbidden)
    body = _ingest_link(monkeypatch, "Analyst hiring at Fallbackco Ltd", "Jobs & Gigs", "green", [])
    assert body["company"] == "Fallbackco Ltd"
    assert "provider_warning" in body


def test_store_survives_reload_and_accept_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv("THENAG_STORE_PATH", str(tmp_path / "store.json"))
    item = _ingest_link(monkeypatch, "Analyst hiring at Persistco Ltd", "Jobs & Gigs", "green", [])
    client.post(f"/api/opportunities/{item['id']}/action", json={"action": "accepted"})
    state = app_module._load_store(app_module.load_state(False))  # what a fresh process does at startup
    restored = next(o for o in state["opportunities"] if o["id"] == item["id"])
    assert restored["status"] == "accepted" and restored["notion_page_id"]
    assert any(a["opportunity_id"] == item["id"] for a in state["actions"])


def _capture_hindsight(monkeypatch, responses):
    from memory import providers as mp
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append((req.get_method(), req.full_url, json.loads(req.data or b"{}"), dict(req.header_items())))
        status, body = responses.pop(0)
        if status != 200:
            raise mp.error.HTTPError(req.full_url, status, "err", {}, io.BytesIO(b'{"detail":"missing"}'))
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(mp.request, "urlopen", fake_urlopen)
    return calls


def test_hindsight_retain_recall_use_official_paths_and_shapes(monkeypatch):
    from memory import HindsightCloudProvider
    monkeypatch.setenv("HINDSIGHT_API_URL", "https://hs.example/")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "k")
    calls = _capture_hindsight(monkeypatch, [
        (404, {}), (200, {}), (200, {"success": True}),  # retain: bank missing -> create -> retry
        (200, {"results": [{"id": "1", "text": "likes remote", "context": 'thenag-meta:{"kind": "preference"}'}]}),
    ])
    provider = HindsightCloudProvider()
    provider.remember("u1", "likes remote", {"kind": "preference"})
    method, url, body, headers = calls[0]
    assert (method, url) == ("POST", "https://hs.example/v1/default/banks/thenag-user-u1/memories")
    assert body["items"][0]["content"] == "likes remote" and body["items"][0]["context"].startswith("thenag-meta:")
    assert headers["Authorization"] == "Bearer k" and headers["User-agent"] == "TheNag/1.0"
    assert calls[1][:2] == ("PUT", "https://hs.example/v1/default/banks/thenag-user-u1")
    memories = provider.recall("u1", "remote")
    assert calls[3][1].endswith("/banks/thenag-user-u1/memories/recall") and calls[3][2]["query"] == "remote"
    assert memories[0]["metadata"] == {"kind": "preference"} and memories[0]["text"] == "likes remote"


def test_hindsight_recall_404_means_no_memories(monkeypatch):
    from memory import HindsightSourceTrustProvider
    monkeypatch.setenv("HINDSIGHT_API_URL", "https://hs.example")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "k")
    _capture_hindsight(monkeypatch, [(404, {})])
    assert HindsightSourceTrustProvider().recall("@x") == []


def test_link_source_creator_comes_from_reel_metadata(monkeypatch):
    extraction = {**_fake_extraction(), "source_creator": "dmart_careers"}
    monkeypatch.setattr(app_module, "run_extraction", lambda url: extraction)
    monkeypatch.setattr(app_module, "classify_extraction", lambda e: _classification("Jobs & Gigs", "green"))
    body = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/M/"}).json()
    assert body["source_creator"] == "@dmart_careers"


def test_title_at_company_does_not_repeat_company():
    from actions import title_at_company
    assert title_at_company("Multiple Positions at DMart Hosakote", "DMart") == "Multiple Positions at DMart Hosakote"
    assert title_at_company("Analyst", "Acme") == "Analyst at Acme"
    assert title_at_company("", "Acme") == "Acme"


def test_confirm_date_creates_calendar_event_for_yellow_deadline(monkeypatch):
    yellow = [{"date": "2026-11-20", "date_type": "application_deadline", "confidence": "yellow", "raw_text": "next Friday", "source": "caption"}]
    item = _ingest_link(monkeypatch, "Analyst hiring at Yellowco Ltd, apply by next Friday", "Jobs & Gigs", "green", yellow)
    accepted = client.post(f"/api/opportunities/{item['id']}/action", json={"action": "accepted"}).json()
    assert accepted["action_result"]["kind"] == "note_only"
    body = client.post(f"/api/opportunities/{item['id']}/confirm-date").json()
    assert body["deadline_confidence"] == "green" and body["action_result"]["calendar_event_id"]
    assert any("calendar" in c["label"].lower() for c in body["confirmation"])
    assert client.post("/api/opportunities/nope/confirm-date").status_code == 404


def test_compensation_keeps_unit_and_period():
    from pipeline import heuristic_extract, normalize_compensation
    assert normalize_compensation("8 LPA") == "8 LPA"
    assert normalize_compensation("₹8,00,000 per annum") == "₹8,00,000 per annum"
    assert normalize_compensation("25k/month stipend") == "25k/month stipend"
    assert normalize_compensation("INR 8") == "Not specified"
    assert normalize_compensation("8") == "Not specified"
    assert normalize_compensation("Unpaid") == "Unpaid"
    assert heuristic_extract("Python developer hiring at Acme Corp, salary 8 LPA")["compensation"] == "8 LPA"
    assert heuristic_extract("Python developer hiring at Acme Corp, apply by 12 October")["compensation"] == "Not provided"


def test_llm_compensation_is_normalized(monkeypatch):
    class FakeGroq:
        def extract(self, text):
            return {"compensation": "INR 8"}

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(app_module, "GroqOpportunityExtractor", FakeGroq)
    body = _ingest_link(monkeypatch, "Analyst hiring at Payco Ltd", "Jobs & Gigs", "green", [])
    assert body["compensation"] == "Not specified"


def test_placeholder_creator_is_treated_as_missing(monkeypatch):
    extraction = {**_fake_extraction("Analyst hiring at Ghostco Ltd"), "source_creator": "reel_owner"}
    monkeypatch.setattr(app_module, "run_extraction", lambda url: extraction)
    monkeypatch.setattr(app_module, "classify_extraction", lambda e: _classification("Jobs & Gigs", "green"))
    body = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/P/", "source_creator": "User"}).json()
    assert body["source_creator"] == "@reel_owner"
    extraction["source_creator"] = None
    body = client.post("/api/process-link", json={"url": "https://www.instagram.com/reel/P/"}).json()
    assert body["source_creator"] == "Unknown source"
