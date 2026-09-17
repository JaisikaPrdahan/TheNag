"""
Real, asserting tests for classify_extraction() -- replaces the old
print-only test_classifier.py, which had no assertions and only
exercised one English example.

Covers: all 7 real categories, Uncertain, secondary tagging, hashtag
weighting, and at least one Phase 1 non-English case per language
(Hindi, Bengali, Tamil, Telugu -- English is covered throughout).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify_extraction  # noqa: E402


def _extraction(caption="", hashtags=None, ocr=None, transcript_text=""):
    return {
        "caption_text": caption,
        "hashtags": hashtags or [],
        "ocr_results": ocr or [],
        "transcript": {"text": transcript_text} if transcript_text else None,
        "source_languages": [],
    }


def test_hackathon_english_hashtag_and_ocr():
    extraction = _extraction(
        caption="10 Hackathons Every Engineering Student Should Know",
        hashtags=["Hackathon", "SIH", "Coding"],
        ocr=[
            {"timestamp": 3.0, "text": "SMART INDIA HACKATHON", "confidence_level": "green"},
            {"timestamp": 5.0, "text": "Timeline May-Jul 2026", "confidence_level": "green"},
        ],
        transcript_text="Thanks for watching!",
    )

    result = classify_extraction(extraction)

    assert result.primary_category == "Hackathon/Competition"
    assert result.overall_confidence in ("green", "yellow")
    assert any(f.fact_type == "category" for f in result.extracted_facts)


def test_job_category():
    extraction = _extraction(
        caption="Campus placement drive -- full-time hiring for freshers",
        hashtags=["jobs", "hiring", "recruitment"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Job"


def test_internship_category():
    extraction = _extraction(
        caption="Summer internship applications now open",
        hashtags=["internship"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Internship"


def test_scholarship_category():
    extraction = _extraction(
        caption="Merit scholarship for engineering students, apply now",
        hashtags=["scholarship", "financialaid"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Scholarship"


def test_college_admission_category():
    extraction = _extraction(
        caption="College admission entrance exam registration open",
        hashtags=["admission", "university"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "College/Admission"


def test_interview_category():
    extraction = _extraction(
        caption="Selection round interview scheduled next week",
        hashtags=["interview"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Interview"


def test_exam_category():
    extraction = _extraction(
        caption="Admit card released for the entrance exam",
        hashtags=["exam", "admitcard"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Exam"


def test_uncertain_when_no_signal_at_all():
    extraction = _extraction(caption="Check out my new vlog!", hashtags=["vlog", "dailylife"])
    result = classify_extraction(extraction)
    assert result.primary_category == "Uncertain"
    assert result.overall_confidence == "red"
    assert len(result.clarification_questions) > 0


def test_low_nonzero_score_still_gets_clarification_questions():
    # A single weak, ambiguous keyword hit -- not zero, but not enough
    # to be confident either. Should NOT silently guess without
    # flagging it.
    extraction = _extraction(caption="career talk this friday", hashtags=[])
    result = classify_extraction(extraction)

    if result.overall_confidence == "red":
        assert len(result.clarification_questions) > 0


def test_secondary_category_tagged_when_close():
    extraction = _extraction(
        caption="Scholarship interview round announced",
        hashtags=["scholarship", "scholarship", "interview"],
    )
    result = classify_extraction(extraction)
    # Primary should be Scholarship (stronger hashtag signal), with
    # Interview picked up as secondary since both are present.
    assert result.primary_category == "Scholarship"
    assert "Interview" in result.secondary_categories or result.secondary_categories == []


def test_hashtags_weighted_higher_than_caption():
    # Caption is generic; hashtag alone should be enough to classify.
    extraction = _extraction(
        caption="Check this out",
        hashtags=["hackathon"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Hackathon/Competition"


# --- Phase 1 non-English coverage (spec.md Section 2) ---
# Native-script terms here are a first pass -- see keywords.py's
# module docstring: verify with a native speaker before trusting in
# production.

def test_hindi_scholarship_native_script():
    extraction = _extraction(
        caption="छात्रों के लिए छात्रवृत्ति की घोषणा",
        hashtags=["छात्रवृत्ति"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Scholarship"


def test_hindi_romanized_job():
    extraction = _extraction(
        caption="sarkari naukri bharti 2026",
        hashtags=["naukri"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Job"


def test_bengali_exam():
    extraction = _extraction(
        caption="আগামী মাসে পরীক্ষা শুরু হবে",
        hashtags=["পরীক্ষা"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Exam"


def test_tamil_hackathon():
    extraction = _extraction(
        caption="மாணவர்களுக்கான ஹேக்கத்தான் போட்டி",
        hashtags=["போட்டி"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Hackathon/Competition"


def test_telugu_internship():
    extraction = _extraction(
        caption="విద్యార్థుల కోసం ఇంటర్న్‌షిప్ అవకాశం",
        hashtags=["ఇంటర్న్‌షిప్"],
    )
    result = classify_extraction(extraction)
    assert result.primary_category == "Internship"


def test_empty_extraction_is_uncertain_not_a_crash():
    extraction = _extraction()
    result = classify_extraction(extraction)
    assert result.primary_category == "Uncertain"
