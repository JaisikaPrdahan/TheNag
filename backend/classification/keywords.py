"""
Category keywords for the memory-first demo. English, Hindi, and
Hindi-English code-switching are the supported languages.

Each category maps to a list of (keyword, language) tuples. Keywords
include:
  - the native-script term
  - common Latin-script/"Hinglish"-style transliterations, since
    code-switched captions (e.g. Hindi written in Latin letters) are
    the default case per spec, not an edge case
  - English terms (the original list)

IMPORTANT: the native-script and transliterated terms below were
drafted without a native speaker's review. Per the same standard
engineering-decisions.md applied to Whisper output ("still unverified:
whether the output is actually correct content-wise, a native speaker
needs to confirm"), these should be checked against real reel samples
in each language before this is trusted in production. Treat this as
a first pass, not a validated list -- flag any wrong/awkward terms and
fix them here rather than working around them in classifier.py.

Keep every keyword in a category's list unique. classify_extraction()
dedupes defensively before scoring, but a repeated keyword here is
still a bug in this data -- it signals the term was meant to carry
independent weight when it can't, and it's confusing to read.
"""

# category -> list of keywords (any script/language, lowercase where
# the script has a case distinction). Matching is substring-based
# (see classifier.py normalise()), so keep multi-word phrases as-is
# and single words unambiguous where possible.

CATEGORIES = {
    "Jobs & Gigs": [
        # English
        "job", "jobs", "hiring", "vacancy", "recruitment", "career",
        "full-time", "fresher hiring", "freelance", "gig", "contract",
        # Hindi (Devanagari + romanized)
        "नौकरी", "भर्ती", "रोजगार", "naukri", "bharti", "rozgar",
        # Bengali
        "চাকরি", "নিয়োগ", "chakri", "niyog",
        # Tamil
        "வேலை", "பணி", "velai", "pani",
        # Internships remain valid when they are work opportunities.
        # Internships remain valid when they are work opportunities.
        "internship", "intern", "interns",
        "इंटर्नशिप", "internship karo",
    ],
    "Interviews & Hiring Drives": [
        "interview", "selection round", "personal interview", "pi round",
        "walk-in interview", "walk in", "hiring drive", "recruitment drive",
        "साक्षात्कार", "इंटरव्यू", "sakshatkar",
        "मेगा ड्राइव", "भर्ती अभियान",
    ],
    "Uncertain": [],
}

# Which language(s) a keyword hints at, used only for evidence/debugging
# (not required for scoring). Kept intentionally simple.
PHASE_1_LANGUAGES = ["hindi", "english"]
