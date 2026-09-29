"""Memory-aware opportunity processing, ranking, and explanation."""

from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher


JOB_MARKERS = ("hiring", "job", "role", "vacancy", "gig", "freelance", "internship", "नौकरी", "भर्ती", "काम")
DRIVE_MARKERS = ("walk-in", "walk in", "interview", "hiring drive", "मेगा ड्राइव", "इंटरव्यू", "साक्षात्कार")
REMOTE_MARKERS = ("remote", "work from home", "wfh", "घर से", "रिमोट")
SKILLS = ("react", "python", "javascript", "typescript", "sql", "figma", "excel", "sales", "writing", "node", "django", "aws")


def _first(pattern: str, text: str, default: str = "Not provided") -> str:
    match = re.search(pattern, text, re.I)
    return match.group(1).strip(" .,-") if match else default


def _confident(value: str, min_len: int = 3) -> str:
    """Returns "" for fragments (too short, or starting mid-word in lowercase)."""
    value = (value or "").strip(" .,-")
    if len(value) < min_len or not value[0].isupper():
        return ""
    return value


def heuristic_extract(caption: str) -> dict:
    text = " ".join((caption or "").split())
    lower = text.lower()
    category = "Interviews & Hiring Drives" if any(k in lower for k in DRIVE_MARKERS) else (
        "Jobs & Gigs" if any(k in lower for k in JOB_MARKERS) else "Uncertain"
    )
    company = _confident(_first(r"(?:\b(?:at|for)\b|@|\bcompany[:\s]+)\s*([A-Z][A-Za-z0-9 &.-]{2,35})", text, ""))
    title = _confident(_first(r"(?:\bhiring\b|\bopening for\b|\brole[:\s]+|\bposition[:\s]+)\s*(?:a|an)?\s*([A-Za-z][A-Za-z /&+-]{2,45}?)(?:\s+(?:at|for|in|—|-)|[.!]|$)", text, ""))
    if category == "Uncertain":
        company = title = ""  # no job signal at all: any match is a fragment, not a listing
    deadline = _first(r"(?:deadline|apply by|last date)[:\s-]+([0-9]{1,2}[ /-][A-Za-z0-9]+(?:[ /-][0-9]{2,4})?)", text, "Not provided")
    location = _first(r"(?:location|in)[:\s-]+(Bengaluru|Bangalore|Mumbai|Delhi|Hyderabad|Pune|Chennai|Noida|Gurugram|Gurgaon|Kolkata)", text)
    compensation = _first(r"((?:₹|INR|Rs\.?)[\s]?[0-9,.]+(?:\s*(?:LPA|per month|/month|/project))?)", text)
    links = re.findall(r"https?://[^\s)]+", text)
    source = _first(r"(?:source|creator|posted by)[:\s@]+([A-Za-z0-9_.-]+)", text, "caption upload")
    evidence = [segment.strip() for segment in re.split(r"[.!\n]", text) if segment.strip()][:4]
    filled = sum(bool(value) and value != "Not provided" for value in (title, company, location, deadline, compensation))
    return {
        "title": title,
        "company": company,
        "location": location,
        "work_mode": "Remote" if any(k in lower for k in REMOTE_MARKERS) else ("On-site" if location != "Not provided" else "Not specified"),
        "employment_type": "Freelance" if "freelance" in lower or "gig" in lower else ("Internship" if "intern" in lower else "Full-time"),
        "skills": [skill.title() for skill in SKILLS if skill in lower],
        "experience": _first(r"([0-9]+(?:-[0-9]+)?\+?\s*(?:years?|yrs?)(?:\s+experience)?)", text),
        "compensation": compensation,
        "deadline": deadline,
        "application_link": links[0] if links else "Not provided",
        "source_creator": source,
        "category": category,
        "evidence": evidence,
        "extraction_confidence": min(94, 48 + filled * 8 + min(len(evidence), 3) * 2),
        "language": "Hindi / Hinglish" if re.search(r"[\u0900-\u097F]", text) else "English",
    }

def duplicate_status(current: dict, opportunities: list[dict]) -> dict:
    best = None
    best_ratio = 0.0
    needle = f"{current['title']} {current['company']}".strip().lower()
    if not needle:
        return {"status": "new", "label": "New opportunity", "changes": []}
    for previous in opportunities:
        ratio = SequenceMatcher(None, needle, f"{previous.get('title', '')} {previous.get('company', '')}".lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = previous, ratio
    if not best or best_ratio < 0.64:
        return {"status": "new", "label": "New opportunity", "changes": []}
    changes = []
    for field in ("deadline", "location", "work_mode", "compensation"):
        before, after = best.get(field), current.get(field)
        if before and after and before != after and after != "Not provided":
            changes.append({"field": field, "before": before, "after": after})
    same_source = best.get("source_creator") == current.get("source_creator")
    status = "updated" if changes else ("exact" if same_source else "similar_source")
    labels = {
        "updated": "Seen before · details changed",
        "exact": "Exact duplicate",
        "similar_source": "Similar listing · another source",
    }
    return {"status": status, "label": labels[status], "changes": changes, "previous_id": best.get("id")}


def rank_and_explain(opportunity: dict, memories: list[dict], source: dict, duplicate: dict) -> tuple[int, list[str], str]:
    text = f"{opportunity['title']} {' '.join(opportunity['skills'])} {opportunity['location']} {opportunity['work_mode']}".lower()
    score = 62
    reasons = []
    recalled = " ".join(memory.get("text", "") for memory in memories).lower()
    for term, points, reason in (
        ("react", 12, "You previously saved React roles."),
        ("remote", 10, "Remote work matches your remembered preference."),
        ("bengaluru", 7, "Bengaluru is one of your preferred locations."),
        ("frontend", 9, "Frontend roles match your recent saves and applications."),
    ):
        if term in text and term in recalled:
            score += points
            reasons.append(reason)
    if opportunity["work_mode"].lower() == "on-site" and "remote" in recalled:
        score -= 9
        reasons.append("Rank reduced because you usually prefer remote or hybrid work.")
    trust = source.get("trust_score", 65)
    score += round((trust - 65) * 0.22)
    observations = source.get("observation_count", 0)
    if observations:
        reasons.append(f"Source trust is {trust}% from {observations} shared observations.")
    else:
        reasons.append(f"Source trust is {trust}% (default): 0 shared observations for this source yet.")
    if duplicate["status"] == "exact":
        score -= 18
        reasons.append("Rank reduced because you have already seen the same listing.")
    elif duplicate["status"] == "updated":
        score += 3
        reasons.append("Shown again because important listing details changed.")
    score = max(8, min(98, score))
    if not reasons:
        reasons.append("This is a new opportunity with enough detail to review.")
    confidence = round(opportunity["extraction_confidence"] * 0.7 + trust * 0.3)
    reasons.append(f"Combined confidence is {confidence}%: extraction quality plus source history.")
    action = "Review and prepare a draft application" if score >= 75 else ("Save for later review" if score >= 55 else "Skip unless your preferences change")
    return score, reasons, action


def weekly_reflect(actions: list[dict], opportunities: list[dict]) -> dict:
    saved = [a for a in actions if a.get("action") == "saved"]
    accepted = [a for a in actions if a.get("action") == "accepted"]
    skipped = [a for a in actions if a.get("action") in ("skipped", "rejected")]
    by_id = {o["id"]: o for o in opportunities}
    top_skills: dict[str, int] = {}
    for action in saved + accepted:
        for skill in by_id.get(action.get("opportunity_id"), {}).get("skills", []):
            top_skills[skill] = top_skills.get(skill, 0) + 1
    return {
        "period": "Last 7 days",
        "stats": {"saved": len(saved), "accepted": len(accepted), "skipped": len(skipped), "follow_through": f"{round(len(accepted) / max(len(saved), 1) * 100)}%"},
        "insights": [f"You saved {len(saved)} opportunities and moved forward with {len(accepted)}."] if actions else [],
        "skills": [name for name, _ in sorted(top_skills.items(), key=lambda item: item[1], reverse=True)[:5]],
        "nudge": "Shortlist two saved roles for focused applications before adding more." if saved else "",
    }
