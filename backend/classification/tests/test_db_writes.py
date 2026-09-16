"""
Tests db_writes.py logic (correct SQL/params, correct category
mapping, correct commit/rollback behaviour) against a mocked
psycopg2 connection -- no live Postgres needed to run these.
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db_writes  # noqa: E402
from models import ClassifiedFacts, ExtractedFact  # noqa: E402


def _mock_conn(fetchone_result=None):
    conn = MagicMock()
    cursor_cm = MagicMock()
    cursor = MagicMock()
    cursor_cm.__enter__.return_value = cursor
    cursor_cm.__exit__.return_value = False
    conn.cursor.return_value = cursor_cm
    if fetchone_result is not None:
        cursor.fetchone.return_value = fetchone_result
    return conn, cursor


def test_category_db_value_mapping():
    assert db_writes._category_db_value("Hackathon/Competition") == "hackathon_competition"
    assert db_writes._category_db_value("College/Admission") == "college_admission"
    assert db_writes._category_db_value("Uncertain") == "uncertain"


def test_category_db_value_unknown_raises():
    import pytest
    with pytest.raises(ValueError):
        db_writes._category_db_value("Not A Real Category")


def test_log_stage_event_inserts_and_commits_when_owning_connection(monkeypatch):
    conn, cursor = _mock_conn()
    monkeypatch.setattr(db_writes, "get_connection", lambda: conn)

    db_writes.log_stage_event("reel-1", "classifying", "started")

    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "insert into stage_events" in sql
    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_log_stage_event_does_not_commit_or_close_shared_connection():
    conn, cursor = _mock_conn()

    db_writes.log_stage_event("reel-1", "classifying", "started", conn=conn)

    conn.commit.assert_not_called()
    conn.close.assert_not_called()


def test_update_reel_stage_sql(monkeypatch):
    conn, cursor = _mock_conn()

    db_writes.update_reel_stage("reel-1", "classified", conn=conn)

    sql = cursor.execute.call_args[0][0]
    params = cursor.execute.call_args[0][1]
    assert "update reels" in sql
    assert params[0] == "classified"
    assert params[2] == "reel-1"


def test_create_opportunity_inserts_and_returns_id():
    conn, cursor = _mock_conn(fetchone_result={"id": "opp-123"})

    classified = ClassifiedFacts(
        primary_category="Job",
        secondary_categories=["Interview"],
        extracted_facts=[
            ExtractedFact(value="Job", confidence="green", fact_type="category", source="hashtags"),
        ],
    )

    opportunity_id = db_writes.create_opportunity("reel-1", "user-1", classified, conn=conn)

    assert opportunity_id == "opp-123"
    sql = cursor.execute.call_args[0][0]
    params = cursor.execute.call_args[0][1]
    assert "insert into opportunities" in sql
    assert params[0] == "reel-1"
    assert params[1] == "user-1"
    assert params[2] == "job"  # mapped from "Job"


def test_classify_and_persist_happy_path(monkeypatch):
    conn, cursor = _mock_conn(fetchone_result={"id": "opp-999"})
    monkeypatch.setattr(db_writes, "get_connection", lambda: conn)

    extraction = {
        "caption_text": "Campus hiring drive for freshers",
        "hashtags": ["jobs", "hiring"],
        "ocr_results": [],
        "transcript": None,
    }

    opportunity_id = db_writes.classify_and_persist("reel-1", "user-1", extraction)

    assert opportunity_id == "opp-999"
    conn.commit.assert_called()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once()


def test_classify_and_persist_marks_reel_failed_on_error(monkeypatch):
    conn, cursor = _mock_conn()
    monkeypatch.setattr(db_writes, "get_connection", lambda: conn)

    def _boom(*args, **kwargs):
        raise RuntimeError("classification blew up")

    monkeypatch.setattr(db_writes, "create_opportunity", _boom)

    import pytest
    with pytest.raises(RuntimeError):
        db_writes.classify_and_persist(
            "reel-1",
            "user-1",
            {"caption_text": "hiring now", "hashtags": ["jobs"], "ocr_results": [], "transcript": None},
        )

    conn.rollback.assert_called()
    # Last update_reel_stage call should be the 'failed' one.
    update_calls = [c for c in cursor.execute.call_args_list if "update reels" in c[0][0]]
    assert update_calls
    assert update_calls[-1][0][1][0] == "failed"
