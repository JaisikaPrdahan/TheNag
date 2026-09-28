from models import ClassifiedFacts, ExtractedFact
from date_resolver import resolve_dates, parse_post_date
from confidence import category_confidence, needs_clarification
from keywords import CATEGORIES


def normalise(text):
    return text.lower().strip()


def classify_extraction(extraction):
    """
    Person 1 -> Person 2 interface.

    Takes the dictionary returned by:
        backend/extraction/combine.py::run_extraction()

    Returns a ClassifiedFacts object.
    """

    caption = normalise(extraction.get("caption_text") or "")
    hashtags = extraction.get("hashtags") or []
    ocr_results = extraction.get("ocr_results") or []
    transcript_data = extraction.get("transcript") or {}

    hashtag_text = " ".join(normalise(tag) for tag in hashtags)

    ocr_text = " ".join(
        normalise(result.get("text", ""))
        for result in ocr_results
    )

    transcript = normalise(
        transcript_data.get("text", "")
        if isinstance(transcript_data, dict)
        else str(transcript_data)
    )

    scores = {category: 0 for category in CATEGORIES}

    for category, keywords in CATEGORIES.items():
        # Dedupe defensively: a keyword accidentally repeated in
        # keywords.py (e.g. the same English filler word added under
        # more than one language's block by mistake) must not count
        # twice -- that silently inflates one category's score and
        # skews classification without anyone noticing.
        for keyword in set(keywords):
            keyword_norm = normalise(keyword)

            if keyword_norm in caption:
                scores[category] += 2

            if keyword_norm in hashtag_text:
                scores[category] += 3

            if keyword_norm in ocr_text:
                scores[category] += 2

            if keyword_norm in transcript:
                scores[category] += 1

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_category, best_score = ranked[0]
    second_category, second_score = ranked[1]

    if best_score == 0:
        return ClassifiedFacts(
            primary_category="Uncertain",
            overall_confidence="red",
            clarification_questions=[
                "What type of opportunity is this?",
                "Can you provide more context about the opportunity?",
            ],
        )

    confidence = category_confidence(best_score, second_score)

    secondary_categories = []

    if second_score >= 3 and second_score >= best_score - 2:
        secondary_categories.append(second_category)

    # A nonzero-but-weak match still returns a best-guess category
    # (rather than collapsing to Uncertain, which would discard real
    # signal), but per spec.md Section 4's "don't guess, escalate to a
    # human" rule, a red-confidence guess must never be treated as
    # settled -- so it always carries clarifying questions too.
    clarification_questions = []
    if needs_clarification(confidence):
        clarification_questions = [
            f"We're not fully sure this is a {best_category} opportunity "
            "-- can you confirm?",
            "Is there more text/context from the reel you can share?",
        ]

    facts = []

    # Category fact
    facts.append(
        ExtractedFact(
            value=best_category,
            confidence=confidence,
            fact_type="category",
            source="caption/hashtag/ocr/transcript",
            evidence=(
                f"Classification score: {best_score}; "
                f"next category score: {second_score}"
            ),
        )
    )

    # Preserve OCR evidence for Person 3.
    for index, result in enumerate(ocr_results):
        text = result.get("text", "").strip()

        if not text:
            continue

        facts.append(
            ExtractedFact(
                value=text,
                confidence=result.get("confidence_level", "yellow"),
                fact_type="ocr_evidence",
                source=f"ocr:{index}",
                evidence=text,
                timestamp=result.get("timestamp"),
            )
        )

    # Preserve caption as evidence.
    if caption:
        facts.append(
            ExtractedFact(
                value=extraction.get("caption_text"),
                confidence="green",
                fact_type="caption_evidence",
                source="caption",
                evidence=extraction.get("caption_text"),
            )
        )

    # Preserve hashtags as evidence.
    if hashtags:
        facts.append(
            ExtractedFact(
                value=hashtags,
                confidence="green",
                fact_type="hashtag_evidence",
                source="hashtags",
                evidence=", ".join(hashtags),
            )
        )

    # Preserve transcript as evidence.
    if transcript:
        facts.append(
            ExtractedFact(
                value=transcript_data.get("text", ""),
                confidence="yellow",
                fact_type="transcript_evidence",
                source="speech",
                evidence=transcript_data.get("text", ""),
            )
        )

    # FIX: relative dates ("next Friday", "in 2 weeks") must resolve
    # against the reel's own publish date, not whenever classification
    # happens to run -- resolve_dates() previously always received
    # reference_date=None here, silently defaulting to datetime.now()
    # inside date_resolver.py. A reel classified days after posting
    # would then compute the wrong date entirely. post_date comes from
    # combine.py's extraction output (see extraction_output.md) --
    # None only for local-file input, which has no post metadata to
    # read a publish date from in the first place.
    reference_date = parse_post_date(extraction.get("post_date"))
    resolved_dates = resolve_dates(extraction, reference_date=reference_date)

    return ClassifiedFacts(
        primary_category=best_category,
        secondary_categories=secondary_categories,
        extracted_facts=facts,
        resolved_dates=resolved_dates,
        overall_confidence=confidence,
        clarification_questions=clarification_questions,
    )