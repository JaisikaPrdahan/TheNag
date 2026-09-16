"""
Category keywords for classify_extraction(), across the Phase 1
languages locked in docs/spec.md Section 2: Hindi, English, Bengali,
Tamil, Telugu.

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
    "Job": [
        # English
        "job", "jobs", "hiring", "vacancy", "recruitment", "career",
        "full-time", "fresher hiring", "walk-in interview",
        # Hindi (Devanagari + romanized)
        "नौकरी", "भर्ती", "रोजगार", "naukri", "bharti", "rozgar",
        # Bengali
        "চাকরি", "নিয়োগ", "chakri", "niyog",
        # Tamil
        "வேலை", "பணி", "velai", "pani",
        # Telugu
        "ఉద్యోగం", "నియామకం", "udyogam", "niyamakam",
    ],
    "Internship": [
        "internship", "intern", "interns",
        "इंटर्नशिप", "internship karo",
        "ইন্টার্নশিপ",
        "பயிற்சி பணி", "இன்டர்ன்ஷிப்",
        "ఇంటర్న్‌షిప్",
    ],
    "Scholarship": [
        "scholarship", "fellowship", "financial aid", "stipend",
        "छात्रवृत्ति", "chatravritti", "scholarship yojana",
        "বৃত্তি", "britti",
        "உதவித்தொகை", "uthavithodhagai",
        "స్కాలర్‌షిప్", "ఉపకార వేతనం", "upakara vetanam",
    ],
    "College/Admission": [
        "admission", "admissions", "college", "university", "entrance",
        "प्रवेश", "दाखिला", "pravesh", "dakhila",
        "ভর্তি", "bhorti",
        "சேர்க்கை", "serkkai",
        "ప్రవేశం", "praveesham",
    ],
    "Interview": [
        "interview", "selection round", "personal interview", "pi round",
        "साक्षात्कार", "इंटरव्यू", "sakshatkar",
        "সাক্ষাৎকার", "ইন্টারভিউ", "sakkhatkar",
        "நேர்காணல்", "nerkaanal",
        "ఇంటర్వ్యూ",
    ],
    "Exam": [
        "exam", "examination", "test", "admit card", "registration",
        "entrance exam", "board exam", "govt exam", "government exam",
        "परीक्षा", "pariksha", "प्रवेश परीक्षा",
        "পরীক্ষা", "porikkha",
        "தேர்வு", "thervu",
        "పరీక్ష",
    ],
    "Hackathon/Competition": [
        "hackathon", "competition", "challenge", "coding challenge",
        "innovation challenge", "smart india hackathon", "sih",
        "ethindia", "case competition", "quiz competition",
        "प्रतियोगिता", "हैकाथॉन", "pratiyogita",
        "প্রতিযোগিতা",
        "போட்டி", "potti", "ஹேக்கத்தான்",
        "పోటీ", "poti", "హ్యాకథాన్",
    ],
}

# Which language(s) a keyword hints at, used only for evidence/debugging
# (not required for scoring). Kept intentionally simple.
PHASE_1_LANGUAGES = ["hindi", "english", "bengali", "tamil", "telugu"]
