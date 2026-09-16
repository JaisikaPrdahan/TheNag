import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from date_resolver import resolve_dates  # noqa: E402


REFERENCE = datetime(2026, 9, 14)  # a Monday


def _extraction(caption="", ocr=None, transcript_text=""):
    return {
        "caption_text": caption,
        "ocr_results": ocr or [],
        "transcript": {"text": transcript_text} if transcript_text else None,
    }


def test_explicit_date_from_caption_is_green():
    extraction = _extraction(caption="Apply by 15 September 2026")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    dates = [r for r in resolved if r.get("date") == "2026-09-15"]
    assert dates
    assert dates[0]["confidence"] == "green"
    assert dates[0]["date_type"] == "application_deadline"


def test_month_range():
    extraction = _extraction(caption="Timeline May-Jul 2026")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    ranges = [r for r in resolved if "start_date" in r]
    assert ranges
    assert ranges[0]["start_date"] == "2026-05-01"
    assert ranges[0]["end_date"] == "2026-07-31"


def test_tomorrow_is_yellow():
    extraction = _extraction(caption="Submit tomorrow")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    tomorrow = [r for r in resolved if r.get("raw_text") == "tomorrow"]
    assert tomorrow
    assert tomorrow[0]["date"] == "2026-09-15"
    assert tomorrow[0]["confidence"] == "yellow"


def test_in_n_days():
    extraction = _extraction(caption="Deadline in 5 days")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    matches = [r for r in resolved if "in 5 days" in r.get("raw_text", "")]
    assert matches
    assert matches[0]["date"] == "2026-09-19"


def test_in_n_weeks_previously_unhandled():
    # spec.md Section 4's own example -- this used to not resolve at all.
    extraction = _extraction(caption="Registration closes in 2 weeks")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    matches = [r for r in resolved if "in 2 weeks" in r.get("raw_text", "")]
    assert matches
    assert matches[0]["date"] == "2026-09-28"
    assert matches[0]["confidence"] == "yellow"  # relative -> always yellow


def test_next_friday_previously_unhandled():
    # spec.md Section 4's other example. REFERENCE is a Monday, so
    # "next Friday" should land on that same week's Friday (Sep 18),
    # not the following week's.
    extraction = _extraction(caption="Interview next Friday")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    matches = [r for r in resolved if "next friday" in r.get("raw_text", "").lower()]
    assert matches
    assert matches[0]["date"] == "2026-09-18"
    assert matches[0]["confidence"] == "yellow"


def test_next_weekday_wraps_when_reference_is_that_day():
    # If "next Monday" is said on a Monday, it means the Monday a week
    # later, not today.
    extraction = _extraction(caption="Apply next Monday")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    matches = [r for r in resolved if "next monday" in r.get("raw_text", "").lower()]
    assert matches
    assert matches[0]["date"] == "2026-09-21"


def test_ocr_low_confidence_downgrades_to_yellow_even_for_explicit_date():
    extraction = _extraction(
        ocr=[{"timestamp": 1.0, "text": "15 September 2026", "confidence_level": "yellow"}]
    )
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    dates = [r for r in resolved if r.get("date") == "2026-09-15"]
    assert dates
    assert dates[0]["confidence"] == "yellow"


def test_no_dates_returns_empty_list():
    extraction = _extraction(caption="Just a regular post with no dates")
    resolved = resolve_dates(extraction, reference_date=REFERENCE)
    assert resolved == []
