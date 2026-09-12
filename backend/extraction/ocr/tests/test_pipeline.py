"""
Tests for pipeline.py's near-duplicate deduplication logic.
Run with: python -m pytest tests/test_pipeline.py

These don't require Tesseract or a real video — they test
deduplicate_ocr_results() directly against hand-built fake OCR results,
based on the kind of near-duplicate noise seen in real reel testing
(the same sentence read slightly differently across consecutive frames).
"""

import unittest
from pipeline import deduplicate_ocr_results, _text_similarity


class TestDeduplication(unittest.TestCase):

    def test_exact_duplicates_collapse_to_one(self):
        results = [
            {"text": "SMART INDIA HACKATHON", "timestamp": 1.0, "raw_confidence": 94.0, "confidence_level": "green"},
            {"text": "SMART INDIA HACKATHON", "timestamp": 2.0, "raw_confidence": 94.0, "confidence_level": "green"},
        ]
        deduped = deduplicate_ocr_results(results)
        self.assertEqual(len(deduped), 1)

    def test_near_duplicates_collapse_and_keep_higher_confidence(self):
        # This mirrors what actually happened in real reel testing: the
        # same sentence read with minor OCR noise across frames.
        results = [
            {"text": "MINISTRY OF ROAD TRANSPORT AND HIGHWAYS", "timestamp": 1.0, "raw_confidence": 82.6, "confidence_level": "green"},
            {"text": "MINISTRY OF , ROAD TRANSPORT AND HIGHWAYS", "timestamp": 3.0, "raw_confidence": 95.1, "confidence_level": "green"},
            {"text": "MINISTRY OF ROAD TRANSPORT AND HIGHWAYS", "timestamp": 4.0, "raw_confidence": 93.4, "confidence_level": "green"},
        ]
        deduped = deduplicate_ocr_results(results)
        self.assertEqual(len(deduped), 1)
        # Should have kept the highest-confidence version (95.1 at 3.0s)
        self.assertEqual(deduped[0]["raw_confidence"], 95.1)

    def test_genuinely_different_text_does_not_collapse(self):
        results = [
            {"text": "SMART INDIA HACKATHON", "timestamp": 1.0, "raw_confidence": 94.0, "confidence_level": "green"},
            {"text": "Sirf Ppts nahi", "timestamp": 11.0, "raw_confidence": 92.7, "confidence_level": "green"},
        ]
        deduped = deduplicate_ocr_results(results)
        self.assertEqual(len(deduped), 2)

    def test_empty_input_returns_empty(self):
        self.assertEqual(deduplicate_ocr_results([]), [])

    def test_similarity_ratio_sanity_check(self):
        # Same core phrase, different amounts of surrounding noise —
        # should still score as similar under word-overlap comparison,
        # which was the actual failure case in real reel testing.
        high = _text_similarity(
            "MINISTRY OF ROAD TRANSPORT AND HIGHWAYS",
            "एवं राजमार्ग मंत्रालय MINISTRY OF , ROAD TRANSPORT AND HIGHWAYS"
        )
        self.assertGreater(high, 0.6)

        # Genuinely different sentences — should be low similarity
        low = _text_similarity("SMART INDIA HACKATHON", "Sirf Ppts nahi")
        self.assertLess(low, 0.5)


if __name__ == "__main__":
    unittest.main()