import re
from datetime import datetime, timedelta

from confidence import source_confidence as _source_confidence


def parse_post_date(post_date_value):
    """
    Parses extraction["post_date"] (an ISO 8601 string from
    combine.py, or None for local-file input) into the datetime that
    relative-date resolution should use as its reference point.

    Falls back to the current time only when post_date_value is
    missing or unparseable -- this used to be resolve_dates()'s only
    behavior (a real bug: relative dates like "next Friday" would
    resolve against whenever classification happened to run, not the
    reel's own publish date, silently drifting wrong the longer a reel
    sat in a queue before processing). Now it's strictly a last-resort
    fallback, not the normal case.
    """
    if not post_date_value:
        return datetime.now()

    try:
        return datetime.fromisoformat(post_date_value)
    except (TypeError, ValueError):
        return datetime.now()


MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def _detect_date_type(text, start, end):
    """
    Determines what the date appears to refer to.
    This is deliberately conservative: unknown dates stay unknown.
    """
    context_start = max(0, start - 80)
    context_end = min(len(text), end + 80)
    context = text[context_start:context_end].lower()

    rules = [
        ("application_deadline", [
            "application deadline",
            "apply by",
            "last date to apply",
            "last date",
            "deadline",
            "closing date",
            "applications close",
            "registration closes",
        ]),
        ("registration_deadline", [
            "registration deadline",
            "register by",
            "last date to register",
            "registration ends",
        ]),
        ("exam_date", [
            "exam date",
            "examination date",
            "exam on",
            "test date",
        ]),
        ("interview_date", [
            "interview date",
            "interview on",
            "interviews on",
        ]),
        ("result_date", [
            "result date",
            "results on",
            "result declared",
        ]),
        ("event_date", [
            "event date",
            "event on",
            "competition on",
            "finale",
        ]),
        ("timeline", [
            "timeline",
            "may-july",
            "may to july",
            "august-september",
            "august to september",
        ]),
    ]

    for date_type, keywords in rules:
        if any(keyword in context for keyword in keywords):
            return date_type

    return "unknown"


def _parse_single_date(match, reference_date):
    """
    Parses dates such as:
    15 September 2026
    September 15, 2026
    15 Sep
    """

    text = match.group(0).strip()

    patterns = [
        r"(?P<day>\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(?P<month>[A-Za-z]+)(?:\s*,?\s*(?P<year>\d{4}))?",

        r"(?P<month>[A-Za-z]+)\s+"
        r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
        r"(?:\s*,?\s*(?P<year>\d{4}))?",
    ]

    for pattern in patterns:
        parsed = re.fullmatch(pattern, text, re.IGNORECASE)

        if not parsed:
            continue

        day = int(parsed.group("day"))
        month_name = parsed.group("month").lower()
        year_text = parsed.group("year")

        if month_name not in MONTHS:
            return None

        month = MONTHS[month_name]
        year = int(year_text) if year_text else reference_date.year

        try:
            date_value = datetime(year, month, day).date()

            # If no year was provided and the date has already passed,
            # assume the next occurrence.
            if not year_text and date_value < reference_date.date():
                date_value = datetime(year + 1, month, day).date()

            return date_value.isoformat()

        except ValueError:
            return None

    return None


def _parse_month_range(match, reference_date):
    """
    Parses:
    May-Jul 2026
    May to July 2026
    August-September 2026
    """

    text = match.group(0).strip()

    pattern = (
        r"(?P<start_month>[A-Za-z]+)"
        r"\s*(?:-|–|—|to)\s*"
        r"(?P<end_month>[A-Za-z]+)"
        r"(?:\s+(?P<year>\d{4}))?"
    )

    parsed = re.fullmatch(pattern, text, re.IGNORECASE)

    if not parsed:
        return None

    start_name = parsed.group("start_month").lower()
    end_name = parsed.group("end_month").lower()

    if start_name not in MONTHS or end_name not in MONTHS:
        return None

    start_month = MONTHS[start_name]
    end_month = MONTHS[end_name]
    year = int(parsed.group("year") or reference_date.year)

    start_date = datetime(year, start_month, 1).date()

    # Calculate the final day of the ending month.
    if end_month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, end_month + 1, 1)

    end_date = next_month.date() - timedelta(days=1)

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def _next_weekday_date(reference_date, target_weekday):
    """
    The next occurrence of `target_weekday` (0=Monday..6=Sunday)
    strictly after reference_date -- "next Friday" said on a Friday
    means the Friday a week later, not today.
    """
    days_ahead = (target_weekday - reference_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return reference_date + timedelta(days=days_ahead)


def _resolve_relative_dates(text, reference_date):
    """
    Handles basic relative expressions.
    These are always yellow because interpretation depends on
    the reference/post date.
    """

    results = []
    lower = text.lower()

    if "tomorrow" in lower:
        results.append({
            "date": (reference_date + timedelta(days=1)).date().isoformat(),
            "raw_text": "tomorrow",
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    if "day after tomorrow" in lower:
        results.append({
            "date": (reference_date + timedelta(days=2)).date().isoformat(),
            "raw_text": "day after tomorrow",
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    for match in re.finditer(
        r"\bin\s+(\d+)\s+days?\b",
        lower,
        re.IGNORECASE,
    ):
        days = int(match.group(1))

        results.append({
            "date": (reference_date + timedelta(days=days)).date().isoformat(),
            "raw_text": match.group(0),
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    # "in N weeks" / "in a week" / "in 1 week" -- spec.md Section 4's
    # own cited example ("in 2 weeks") wasn't previously handled at all.
    for match in re.finditer(
        r"\bin\s+(\d+)\s+weeks?\b",
        lower,
        re.IGNORECASE,
    ):
        weeks = int(match.group(1))

        results.append({
            "date": (reference_date + timedelta(weeks=weeks)).date().isoformat(),
            "raw_text": match.group(0),
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    if re.search(r"\bin\s+a\s+week\b", lower):
        results.append({
            "date": (reference_date + timedelta(weeks=1)).date().isoformat(),
            "raw_text": "in a week",
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    # "next Friday" / "next monday" etc -- spec.md Section 4's other
    # cited example, also not previously handled.
    for match in re.finditer(
        r"\bnext\s+(" + "|".join(WEEKDAYS.keys()) + r")\b",
        lower,
        re.IGNORECASE,
    ):
        weekday_name = match.group(1).lower()
        target_weekday = WEEKDAYS[weekday_name]

        resolved_date = _next_weekday_date(reference_date, target_weekday)

        results.append({
            "date": resolved_date.date().isoformat(),
            "raw_text": match.group(0),
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    if "next week" in lower:
        results.append({
            "date": (reference_date + timedelta(weeks=1)).date().isoformat(),
            "raw_text": "next week",
            "date_type": "unknown",
            "confidence": "yellow",
            "resolution_method": "relative",
        })

    return results


def resolve_dates(extraction, reference_date=None):
    """
    Main Person 2 date-resolution entry point.

    Takes Person 1's extraction output and returns a list of
    structured date objects for ClassifiedFacts.resolved_dates.

    reference_date should normally be parse_post_date(extraction.get(
    "post_date")) -- the caller (classifier.py) is responsible for
    passing it, since that's where extraction is first unpacked.
    Defaulting to None here (which falls through to datetime.now()
    below) exists only as a safety net for direct/test callers, not
    as the intended normal path.
    """

    if reference_date is None:
        reference_date = datetime.now()

    sources = []

    caption = extraction.get("caption_text") or ""
    if caption.strip():
        sources.append({
            "text": caption,
            "source": "caption",
            "confidence": "green",
        })

    for result in extraction.get("ocr_results") or []:
        text = result.get("text", "")
        if text.strip():
            sources.append({
                "text": text,
                "source": "ocr",
                "confidence": result.get("confidence_level", "yellow"),
                "timestamp": result.get("timestamp"),
            })

    transcript = extraction.get("transcript") or {}
    if isinstance(transcript, dict):
        transcript_text = transcript.get("text", "")
    else:
        transcript_text = str(transcript)

    if transcript_text.strip():
        sources.append({
            "text": transcript_text,
            "source": "speech",
            "confidence": "yellow",
        })

    resolved = []
    seen = set()

    month_range_pattern = (
        r"\b(?:January|Jan|February|Feb|March|Mar|April|Apr|May|"
        r"June|Jun|July|Jul|August|Aug|September|Sep|Sept|October|"
        r"Oct|November|Nov|December|Dec)"
        r"\s*(?:-|–|—|to)\s*"
        r"(?:January|Jan|February|Feb|March|Mar|April|Apr|May|"
        r"June|Jun|July|Jul|August|Aug|September|Sep|Sept|October|"
        r"Oct|November|Nov|December|Dec)"
        r"(?:\s+\d{4})?\b"
    )

    single_date_pattern = (
        r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s+"
        r"(?:January|Jan|February|Feb|March|Mar|April|Apr|May|"
        r"June|Jun|July|Jul|August|Aug|September|Sep|Sept|October|"
        r"Oct|November|Nov|December|Dec)"
        r"(?:\s*,?\s*\d{4})?"
        r"|"
        r"(?:January|Jan|February|Feb|March|Mar|April|Apr|May|"
        r"June|Jun|July|Jul|August|Aug|September|Sep|Sept|October|"
        r"Oct|November|Nov|December|Dec)"
        r"\s+\d{1,2}(?:st|nd|rd|th)?"
        r"(?:\s*,?\s*\d{4})?)\b"
    )

    for source_data in sources:
        text = source_data["text"]

        # Month ranges
        for match in re.finditer(
            month_range_pattern,
            text,
            re.IGNORECASE,
        ):
            parsed = _parse_month_range(match, reference_date)

            if not parsed:
                continue

            key = (
                parsed["start_date"],
                parsed["end_date"],
                source_data["source"],
            )

            if key in seen:
                continue

            seen.add(key)

            resolved.append({
                "raw_text": match.group(0),
                "start_date": parsed["start_date"],
                "end_date": parsed["end_date"],
                "date_type": _detect_date_type(
                    text,
                    match.start(),
                    match.end(),
                ),
                "confidence": _source_confidence(
                    source_data["source"],
                    source_data["confidence"],
                ),
                "source": source_data["source"],
                "timestamp": source_data.get("timestamp"),
                "resolution_method": "explicit_range",
            })

        # Single explicit dates
        for match in re.finditer(
            single_date_pattern,
            text,
            re.IGNORECASE,
        ):
            parsed_date = _parse_single_date(
                match,
                reference_date,
            )

            if not parsed_date:
                continue

            key = (
                parsed_date,
                source_data["source"],
            )

            if key in seen:
                continue

            seen.add(key)

            resolved.append({
                "raw_text": match.group(0),
                "date": parsed_date,
                "date_type": _detect_date_type(
                    text,
                    match.start(),
                    match.end(),
                ),
                "confidence": _source_confidence(
                    source_data["source"],
                    source_data["confidence"],
                ),
                "source": source_data["source"],
                "timestamp": source_data.get("timestamp"),
                "resolution_method": "explicit",
            })

        # Relative dates
        relative_dates = _resolve_relative_dates(
            text,
            reference_date,
        )

        for item in relative_dates:
            item["source"] = source_data["source"]
            item["timestamp"] = source_data.get("timestamp")

            key = (
                item["date"],
                item["raw_text"],
                item["source"],
            )

            if key not in seen:
                seen.add(key)
                resolved.append(item)

    return resolved
