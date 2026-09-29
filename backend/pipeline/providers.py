"""Inference provider boundary for Groq and deterministic demo extraction."""

from __future__ import annotations

import json
import logging
import os
from urllib import error, request

logger = logging.getLogger("thenag.groq")
# Groq sits behind Cloudflare, which 403s urllib's default User-Agent.
GROQ_HEADERS = {"User-Agent": "TheNag/1.0", "Accept": "application/json"}


class GroqOpportunityExtractor:
    def __init__(self):
        self.api_key = os.environ["GROQ_API_KEY"]
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.url = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")

    def extract(self, caption: str) -> dict:
        schema = {
            "title": "string", "company": "string", "location": "string",
            "work_mode": "remote|hybrid|on-site|unknown", "employment_type": "string",
            "skills": ["string"], "experience": "string", "compensation": "string",
            "deadline": "YYYY-MM-DD or empty", "application_link": "string",
            "source_creator": "string", "category": "Jobs & Gigs|Interviews & Hiring Drives|Uncertain",
        }
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": f"Extract a job opportunity as JSON matching: {json.dumps(schema)}. Support English, Hindi, and Hinglish. Never invent missing facts."},
                {"role": "user", "content": caption},
            ],
        }
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**GROQ_HEADERS, "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=25) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", "replace")[:500]
            logger.warning("Groq extraction HTTP %s: %s", exc.code, body_text)
            raise RuntimeError(f"Groq extraction failed: HTTP {exc.code}: {body_text}") from exc
        return json.loads(body["choices"][0]["message"]["content"])
