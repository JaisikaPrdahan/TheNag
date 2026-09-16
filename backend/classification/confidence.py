"""
Confidence-tagging rules, per docs/spec.md Section 4:

    green  - clear, confirmed, high-confidence extraction
    yellow - incomplete/uncertain: relative dates (resolved against the
             reel's own post date), or OCR on a not-yet-validated script
    red    - conflicting or unreadable information

Pulled out of classifier.py / date_resolver.py into its own module so
the rules live in one place, matching the module split described in
docs/team-structure.md and the repo's original planned layout.
"""


def category_confidence(best_score, second_score):
    """
    Confidence tier for a category classification, given the winning
    category's keyword-match score and the runner-up's score.

    green:  a clear, well-separated winner (score >= 5, and at least 3
            points ahead of the next category)
    yellow: a real but less decisive signal (score >= 3)
    red:    a weak, low-signal match (nonzero but < 3) -- still a
            guess, not a confident classification. Callers should
            treat a red category the same way as Uncertain for any
            auto-action decision (see spec's "don't guess, escalate to
            a human" rule) even though a best-guess category is still
            returned rather than discarded.
    """
    if best_score >= 5 and best_score >= second_score + 3:
        return "green"
    if best_score >= 3:
        return "yellow"
    return "red"


def source_confidence(source, base_confidence):
    """
    Confidence for a date/fact pulled from a given source.

    Caption text is treated as more trustworthy than a low-confidence
    OCR read (see docs/engineering-decisions.md: caption is often the
    cleanest source). Anything not already green from its own pipeline
    (e.g. OCR confidence_level from Person 1) is downgraded to yellow
    rather than assumed reliable.
    """
    if source == "caption":
        return "green"

    if base_confidence == "green":
        return "green"

    return "yellow"


def needs_clarification(confidence):
    """
    True when a confidence tier is low enough that the result should
    never be auto-actioned without surfacing it to the user first --
    per spec.md Section 4's hard rule (applied here to category
    confidence, not just dates).
    """
    return confidence == "red"
