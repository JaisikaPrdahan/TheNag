"""
Tests for url_downloader.py's extract_hashtags() logic.
Run with: python -m pytest tests/test_url_downloader.py

Doesn't require network access or a real download — tests the pure
text-parsing logic in isolation.
"""

import unittest
from url_downloader import extract_hashtags


class TestExtractHashtags(unittest.TestCase):

    def test_extracts_multiple_hashtags(self):
        caption = "Apply now! #hiring #scholarship2026 #students"
        result = extract_hashtags(caption)
        self.assertEqual(result, ["hiring", "scholarship2026", "students"])

    def test_no_hashtags_returns_empty_list(self):
        caption = "Apply now, link in bio!"
        self.assertEqual(extract_hashtags(caption), [])

    def test_none_caption_returns_empty_list(self):
        self.assertEqual(extract_hashtags(None), [])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(extract_hashtags(""), [])

    def test_hashtags_mixed_with_other_text(self):
        caption = "Hiring 2025 #softwarehiring winning tips #github #coding tips inside"
        result = extract_hashtags(caption)
        self.assertEqual(result, ["softwarehiring", "github", "coding"])


if __name__ == "__main__":
    unittest.main()
