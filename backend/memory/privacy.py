"""PII minimisation applied before anything enters long-term memory."""

import re


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


def redact_for_memory(value: str) -> tuple[str, list[dict]]:
    """Return redacted text and a safe audit log that never contains the PII."""
    text = value or ""
    events: list[dict] = []

    def replace_email(_match):
        events.append({"type": "email", "replacement": "[REDACTED_EMAIL]"})
        return "[REDACTED_EMAIL]"

    def replace_phone(_match):
        events.append({"type": "phone", "replacement": "[REDACTED_PHONE]"})
        return "[REDACTED_PHONE]"

    text = EMAIL_PATTERN.sub(replace_email, text)
    text = PHONE_PATTERN.sub(replace_phone, text)
    return text, events
