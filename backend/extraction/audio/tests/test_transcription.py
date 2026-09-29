"""
Tests for transcription.py's language-code lookup logic.
Run with: python -m pytest tests/test_transcription.py

These don't require Whisper to actually run (no model loading, no real
audio) — they test get_whisper_language_code() in isolation. Testing
against a real reel is a manual step, see the README.
"""

import unittest
from unittest.mock import patch

from transcription import (
    LANGUAGE_CODE_MAP,
    PHASE_1_LANGUAGES,
    get_whisper_language_code,
    transcribe_audio,
)


class TestLanguageCodeLookup(unittest.TestCase):

    def test_known_language_returns_correct_code(self):
        self.assertEqual(get_whisper_language_code("hindi"), "hi")
        self.assertEqual(get_whisper_language_code("english"), "en")
        self.assertEqual(get_whisper_language_code("bengali"), "bn")
        self.assertEqual(get_whisper_language_code("tamil"), "ta")
        self.assertEqual(get_whisper_language_code("telugu"), "te")

    def test_none_input_returns_none(self):
        # None means "let Whisper auto-detect" — must not crash or
        # accidentally return a code.
        self.assertIsNone(get_whisper_language_code(None))

    def test_unrecognized_language_returns_none(self):
        # An unknown language name should fall back to auto-detect
        # (None) rather than raising an error.
        self.assertIsNone(get_whisper_language_code("klingon"))

    def test_phase_1_languages_all_have_codes(self):
        # Every language we've actually committed to supporting must
        # have an entry in the code map — this would catch someone
        # adding a language to PHASE_1_LANGUAGES without also adding
        # its Whisper code.
        for lang in PHASE_1_LANGUAGES:
            self.assertIn(lang, LANGUAGE_CODE_MAP)

    def test_local_timeout_terminates_worker_and_skips_transcript(self):
        class HungProcess:
            def __init__(self, *args, **kwargs):
                self.terminated = False

            def start(self):
                pass

            def join(self, timeout=None):
                pass

            def is_alive(self):
                return True

            def terminate(self):
                self.terminated = True

        worker = HungProcess()
        with patch("transcription.multiprocessing.Process", return_value=worker):
            result = transcribe_audio("demo.mp4", timeout_seconds=0.01)

        self.assertIsNone(result)
        self.assertTrue(worker.terminated)


if __name__ == "__main__":
    unittest.main()
