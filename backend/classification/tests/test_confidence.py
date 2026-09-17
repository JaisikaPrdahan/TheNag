import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from confidence import category_confidence, source_confidence, needs_clarification  # noqa: E402


def test_category_confidence_green_for_decisive_win():
    assert category_confidence(best_score=6, second_score=1) == "green"


def test_category_confidence_yellow_for_moderate_score():
    assert category_confidence(best_score=3, second_score=2) == "yellow"


def test_category_confidence_red_for_weak_score():
    assert category_confidence(best_score=1, second_score=0) == "red"


def test_category_confidence_yellow_when_close_race_even_if_high():
    # High score but not well-separated from the runner-up -> not green.
    assert category_confidence(best_score=6, second_score=5) == "yellow"


def test_source_confidence_caption_always_green():
    assert source_confidence("caption", "yellow") == "green"
    assert source_confidence("caption", "red") == "green"


def test_source_confidence_passes_through_green():
    assert source_confidence("ocr", "green") == "green"


def test_source_confidence_downgrades_non_green():
    assert source_confidence("ocr", "yellow") == "yellow"
    assert source_confidence("speech", "red") == "yellow"


def test_needs_clarification_only_for_red():
    assert needs_clarification("red") is True
    assert needs_clarification("yellow") is False
    assert needs_clarification("green") is False
