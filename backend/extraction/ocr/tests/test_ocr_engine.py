"""
Basic tests for the OCR subsystem's non-video-dependent logic.
Run with: python -m pytest test_ocr_engine.py
(or: python -m unittest test_ocr_engine.py)

These don't require Tesseract or a real video file — they test the
language-string building and confidence-scoring logic in isolation.
Testing against a real reel is a manual step, see the README.
"""

import unittest
from ocr_engine import get_tesseract_lang_string, confidence_to_level


class TestOCREngine(unittest.TestCase):

    def test_lang_string_defaults_to_phase1(self):
        result = get_tesseract_lang_string()
        self.assertIn("hin", result)
        self.assertIn("eng", result)
        self.assertIn("ben", result)
        self.assertIn("tam", result)
        self.assertIn("tel", result)

    def test_lang_string_with_specific_languages(self):
        result = get_tesseract_lang_string(["hindi", "english"])
        self.assertEqual(result, "hin+eng")

    def test_confidence_levels_validated_script(self):
        self.assertEqual(confidence_to_level(80, script_is_validated=True), "green")
        self.assertEqual(confidence_to_level(60, script_is_validated=True), "yellow")
        self.assertEqual(confidence_to_level(20, script_is_validated=True), "red")

    def test_confidence_levels_unvalidated_script(self):
        # Even a high raw score should not exceed yellow for a script
        # we haven't validated yet (e.g. an eventual Phase 2 language).
        self.assertEqual(confidence_to_level(90, script_is_validated=False), "yellow")
        self.assertEqual(confidence_to_level(30, script_is_validated=False), "red")


if __name__ == "__main__":
    unittest.main()