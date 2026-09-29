"""Classifier regression tests for the working-professional product scope."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify_extraction  # noqa: E402


def extraction(caption="", hashtags=None, ocr=None, transcript=""):
    return {
        "caption_text": caption,
        "hashtags": hashtags or [],
        "ocr_results": ocr or [],
        "transcript": {"text": transcript} if transcript else None,
        "source_languages": [],
    }


def test_jobs_and_gigs_for_english_react_role():
    result = classify_extraction(extraction(
        "Remote React developer job hiring now",
        ["jobs", "hiring"],
        [{"text": "FULL TIME REACT ROLE", "confidence_level": "green"}],
    ))
    assert result.primary_category == "Jobs & Gigs"
    assert result.overall_confidence in ("green", "yellow")


def test_interviews_and_drives_for_walk_in():
    result = classify_extraction(extraction("Walk-in interview hiring drive for software roles", ["interview"]))
    assert result.primary_category == "Interviews & Hiring Drives"


def test_hindi_and_hinglish_job_content():
    result = classify_extraction(extraction("React developer की भर्ती, remote naukri", ["naukri", "hiring"]))
    assert result.primary_category == "Jobs & Gigs"


def test_uncertain_when_there_is_no_opportunity_signal():
    result = classify_extraction(extraction("A quiet day in my life", ["vlog"]))
    assert result.primary_category == "Uncertain"
    assert result.overall_confidence == "red"
    assert result.clarification_questions


def test_preserves_caption_and_ocr_evidence():
    result = classify_extraction(extraction(
        "Python developer role", ["jobs"],
        [{"timestamp": 4.0, "text": "APPLY BY 12 OCT", "confidence_level": "green"}],
    ))
    evidence_types = {fact.fact_type for fact in result.extracted_facts}
    assert {"category", "caption_evidence", "hashtag_evidence", "ocr_evidence"} <= evidence_types
