"""
Regression test for a real bug: classify_extraction() previously
always called resolve_dates(extraction) with no reference_date,
so relative dates ("next Friday", "in 2 weeks") silently resolved
against datetime.now() at classification time instead of the reel's
own publish date -- drifting wrong the longer a reel sat in a queue
before being processed.

Run with: pytest tests/test_post_date_regression.py -v
"""

from datetime import datetime, timedelta

from classifier import classify_extraction
from date_resolver import parse_post_date


def test_relative_date_resolves_against_post_date_not_now():
    # The reel was posted 10 days ago and says "next Friday" in its
    # caption. If reference_date is wired correctly, the resolved
    # date should be calculated relative to the post date -- NOT
    # relative to today, which would be a materially different date
    # after a 10-day gap.
    post_date = (datetime.now() - timedelta(days=10)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    extraction = {
        "caption_text": "Apply by next Friday for this internship!",
        "hashtags": ["internship"],
        "post_date": post_date.isoformat(),
        "ocr_results": [],
        "transcript": None,
    }

    result = classify_extraction(extraction)

    resolved_relative_dates = [
        f for f in result.extracted_facts
        if f.fact_type not in ("category", "caption_evidence", "hashtag_evidence")
    ]

    # The actual date resolution isn't folded into extracted_facts by
    # classify_extraction() directly -- it lives in the returned
    # ClassifiedFacts.resolved_dates. Check that instead.
    assert len(result.resolved_dates) >= 1

    relative_date_entry = next(
        (d for d in result.resolved_dates if d.get("resolution_method") == "relative"),
        None,
    )
    assert relative_date_entry is not None, "Expected 'next Friday' to resolve as a relative date"

    # Compute what "next Friday" SHOULD be relative to post_date.
    days_ahead = (4 - post_date.weekday()) % 7  # Friday = 4
    if days_ahead == 0:
        days_ahead = 7
    expected_date = (post_date + timedelta(days=days_ahead)).date().isoformat()

    assert relative_date_entry["date"] == expected_date, (
        f"Expected 'next Friday' to resolve to {expected_date} (relative to the "
        f"10-days-ago post date), but got {relative_date_entry['date']}. "
        f"This means reference_date isn't being threaded through correctly -- "
        f"check that classify_extraction() is calling parse_post_date() and "
        f"passing it to resolve_dates()."
    )

    # Also confirm it's NOT accidentally resolved relative to today
    # (the old buggy behavior) -- these two dates should differ given
    # the 10-day gap, unless today happens to also be a Friday, which
    # this assertion would then wrongly pass on; the primary assertion
    # above is the real test, this is just an extra sanity check.
    today_days_ahead = (4 - datetime.now().weekday()) % 7
    if today_days_ahead == 0:
        today_days_ahead = 7
    wrong_date_if_buggy = (datetime.now() + timedelta(days=today_days_ahead)).date().isoformat()

    if expected_date != wrong_date_if_buggy:
        assert relative_date_entry["date"] != wrong_date_if_buggy


def test_parse_post_date_falls_back_to_now_when_missing():
    # Local-file input has no post_date at all -- must not crash, and
    # must fall back to a real datetime, not None.
    result = parse_post_date(None)
    assert isinstance(result, datetime)


def test_parse_post_date_falls_back_to_now_when_unparseable():
    # Defensive case: a malformed string should not crash classify_extraction()
    result = parse_post_date("not-a-real-date")
    assert isinstance(result, datetime)


def test_parse_post_date_parses_real_iso_string():
    result = parse_post_date("2026-09-01T12:00:00")
    assert result.year == 2026
    assert result.month == 9
    assert result.day == 1