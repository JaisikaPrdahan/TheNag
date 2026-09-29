import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app import app


client = TestClient(app)


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


def test_action_updates_private_memory_with_redaction():
    response = client.post("/api/opportunities/opp-01/action", json={
        "action": "rejected", "reason": "Contact me at person@example.com or 9876543210",
    })
    assert response.status_code == 200
    redactions = response.json()["memory_redactions"]
    assert {item["type"] for item in redactions} == {"email", "phone"}
