"""TheNag HTTP API.

The API defaults to deterministic demo mode. Real providers are selected only
when their credentials are present, so a missing integration never breaks the
product walkthrough.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("thenag.api")

# Resolve first: test runners can import this module through a path containing
# ``tests/..`` and a purely lexical ``parents`` lookup would otherwise point
# at the test directory instead of the backend directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

# backend/.env fills in anything not already set; real environment variables win.
load_dotenv(BACKEND_DIR / ".env", override=False)

from actions import accept_opportunity, build_calendar_provider, build_notes_provider  # noqa: E402
from memory import DemoMemoryProvider, build_memory_provider, demo_seed_enabled, build_source_trust_provider, redact_for_memory  # noqa: E402
from pipeline import duplicate_status, heuristic_extract, rank_and_explain, weekly_reflect  # noqa: E402
from pipeline.providers import GroqOpportunityExtractor  # noqa: E402

sys.path.insert(0, str(BACKEND_DIR / "classification"))
from classifier import classify_extraction  # noqa: E402


class LinkFetchFailed(Exception):
    """A reel/post URL couldn't be auto-fetched; caller should fall back to caption/upload."""


_extraction_combine_cache: dict = {}


def _load_extraction_combine():
    """Lazily imports backend/extraction's combine module.

    Deferred (rather than a top-level import) so the API can start and be
    tested without extraction's heavy dependencies (Tesseract, FFmpeg,
    PyTorch/Whisper, yt-dlp, instaloader) installed.
    """
    if "run_extraction" not in _extraction_combine_cache:
        sys.path.insert(0, str(BACKEND_DIR / "extraction"))
        import combine as _combine
        _extraction_combine_cache["run_extraction"] = _combine.run_extraction
        _extraction_combine_cache["AutoFetchFailed"] = _combine.AutoFetchFailed
    return _extraction_combine_cache["run_extraction"], _extraction_combine_cache["AutoFetchFailed"]


def run_extraction(media_path_or_url: str) -> dict:
    """Thin, monkeypatchable wrapper around backend/extraction's combine.run_extraction."""
    real_run_extraction, real_auto_fetch_failed = _load_extraction_combine()
    try:
        return real_run_extraction(media_path_or_url)
    except real_auto_fetch_failed as exc:
        raise LinkFetchFailed(str(exc)) from exc


SEED_PATH = BACKEND_DIR / "demo" / "seed.json"
EMPTY_USER = {"id": "demo-user", "name": "", "headline": "", "location": "", "avatar": ""}


def load_state(demo_seed: bool) -> dict:
    """Initial in-memory state. Empty unless DEMO_SEED=true: real Reels and
    real user actions are the only things that should show up by default."""
    if demo_seed:
        return json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {"demo_user": dict(EMPTY_USER), "sources": [], "opportunities": [], "memories": [], "actions": []}


seed = load_state(demo_seed_enabled())
opportunities = seed["opportunities"]
sources = seed["sources"]
source_by_name = {source["name"]: source for source in sources}
memory_provider, memory_mode = build_memory_provider()
source_trust_provider, source_trust_mode = build_source_trust_provider()
calendar_provider, calendar_mode = build_calendar_provider()
notes_provider, notes_mode = build_notes_provider()
inference_mode = "groq" if os.getenv("GROQ_API_KEY") else "demo-heuristics"

app = FastAPI(title="TheNag API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CaptionInput(BaseModel):
    caption: str
    source_creator: str | None = None


class ActionInput(BaseModel):
    action: str
    reason: str | None = None


class LinkInput(BaseModel):
    url: str
    source_creator: str | None = None


def _user(user_id: str | None) -> str:
    return user_id or "demo-user"


def _opportunity_memory_metadata(opportunity_id: str, opportunity: dict) -> dict:
    return {
        "opportunity_id": opportunity_id,
        "title": opportunity.get("title"),
        "company": opportunity.get("company"),
        "deadline": opportunity.get("deadline"),
        "source_creator": opportunity.get("source_creator"),
    }


def _recall_duplicate_hint(user_id: str, title: str, company: str) -> dict | None:
    """Checks private memory for a prior sighting of this title+company that
    isn't in the live in-memory `opportunities` list -- lets "seen before"
    survive a process restart instead of dying with that list."""
    try:
        memories = memory_provider.recall(user_id, f"{title} {company}")
    except Exception:
        logger.warning("Hindsight recall failed during duplicate check for user_id=%s; falling back to the in-memory list only", user_id, exc_info=True)
        return None
    live_ids = {item["id"] for item in opportunities}
    for memory in memories:
        meta = memory.get("metadata", {})
        previous_id = meta.get("opportunity_id")
        if previous_id and previous_id not in live_ids and meta.get("title") == title and meta.get("company") == company:
            return {
                "status": "resurfaced",
                "label": "Seen before — recalled from memory, not from this session",
                "changes": [],
                "previous_id": previous_id,
            }
    return None


def _apply_source_trust(extracted: dict, rank: int, why: list[str]) -> int:
    """Recalls shared, aggregate source-trust facts (never a user's private
    bank -- see backend/memory/README.md) and folds them into rank + the Why
    panel."""
    source_creator = extracted.get("source_creator")
    try:
        facts = source_trust_provider.recall(source_creator)
    except Exception:
        logger.warning("Source-trust recall failed for source_creator=%s", source_creator, exc_info=True)
        return rank
    negative_kinds = {"dead_link", "rejected_as_fake"}
    negative = sum(1 for fact in facts if fact.get("metadata", {}).get("kind") in negative_kinds)
    if negative:
        rank = max(8, rank - 6 * negative)
        why.append(f"Shared source-trust memory has {negative} report(s) of dead or fake listings from {source_creator}.")
    elif facts:
        why.append(f"Shared source-trust memory has {len(facts)} prior observation(s) of {source_creator}, none negative.")
    return rank


def _finalize(extracted: dict, memory_query: str, user_id: str) -> dict:
    source = source_by_name.get(extracted["source_creator"], {
        "name": extracted["source_creator"], "trust_score": 60, "observation_count": 0,
        "assessment": "Not enough history", "evidence": "New source; no shared reliability history yet.",
    })
    try:
        memories = memory_provider.recall(user_id, memory_query)
    except Exception:
        logger.warning("Hindsight recall failed for user_id=%s; falling back to demo memory", user_id, exc_info=True)
        memories = DemoMemoryProvider().recall(user_id, memory_query)
        extracted["memory_warning"] = "Hindsight Cloud was unavailable; demo memory was used."
    duplicate = _recall_duplicate_hint(user_id, extracted["title"], extracted["company"]) or duplicate_status(extracted, opportunities)
    rank, why, next_action = rank_and_explain(extracted, memories, source, duplicate)
    rank = _apply_source_trust(extracted, rank, why)
    opportunity_id = f"processed-{len(opportunities) + 1}"
    result = {
        "id": opportunity_id, **extracted,
        "source_trust": source["trust_score"], "source_detail": source,
        "duplicate": duplicate, "rank": rank, "why": why,
        "recommended_action": next_action, "status": "new",
        # True only when recalled preference/decision memory fed the result; otherwise the Why panel says "Confidence".
        "personalized": any((m.get("metadata") or {}).get("kind") in {"preference", "decision"} for m in memories),
        "draft_only": True, "memory_mode": memory_mode, "inference_mode": inference_mode,
        "recalled_memories": [m.get("text", m.get("content", "Remembered preference")) for m in memories[:4]],
    }
    opportunities.insert(0, result)
    try:
        memory_provider.remember(
            user_id, f"Viewed {result['title']} at {result['company']}",
            {"kind": "viewed", **_opportunity_memory_metadata(opportunity_id, result)},
        )
    except Exception:
        logger.warning("Hindsight retain failed for user_id=%s on ingest", user_id, exc_info=True)
    return result


def _primary_resolved_date(resolved_dates: list[dict]) -> dict | None:
    deadline_types = {"application_deadline", "registration_deadline"}
    for date in resolved_dates:
        if date.get("date_type") in deadline_types:
            return date
    return resolved_dates[0] if resolved_dates else None


def _apply_classified_dates(extracted: dict, classified) -> None:
    """Overlays the classifier's resolved dates (real green/yellow confidence,
    not the un-confidence-tagged deadline heuristic_extract guesses at) onto
    an already heuristic_extract()-ed opportunity dict."""
    extracted["resolved_dates"] = classified.resolved_dates
    primary_date = _primary_resolved_date(classified.resolved_dates)
    if primary_date:
        extracted["deadline"] = primary_date.get("date") or f"{primary_date['start_date']} to {primary_date['end_date']}"
        extracted["deadline_confidence"] = primary_date["confidence"]


LLM_TEXT_LIMIT = 6000
_EMPTY_LLM_VALUES = {"", "unknown", "not provided", "n/a", "none", "null", "not specified"}


def _llm_extract(extracted: dict, text: str) -> None:
    """Overlays Groq's extraction of `text` onto `extracted` (in place),
    ignoring empty/placeholder values so heuristics still fill the gaps."""
    if not os.getenv("GROQ_API_KEY"):
        return
    try:
        result = GroqOpportunityExtractor().extract(text[:LLM_TEXT_LIMIT])
    except Exception:
        extracted["provider_warning"] = "Groq was unavailable; deterministic extraction was used."
        return
    extracted.update({
        k: v for k, v in result.items()
        if v and not (isinstance(v, str) and v.strip().lower() in _EMPTY_LLM_VALUES)
    })


def _process(caption: str, source_creator: str | None, user_id: str) -> dict:
    if not caption.strip():
        raise HTTPException(422, "Caption text is required")
    extracted = heuristic_extract(caption)
    _llm_extract(extracted, caption)
    if source_creator:
        extracted["source_creator"] = source_creator if source_creator.startswith("@") else f"@{source_creator}"
    classified = classify_extraction({"caption_text": caption, "hashtags": [], "post_date": None, "ocr_results": [], "transcript": None})
    _apply_classified_dates(extracted, classified)
    return _finalize(extracted, caption, user_id)


def _combined_text(extraction: dict) -> str:
    parts = [extraction.get("caption_text") or ""]
    parts.extend(result.get("text", "") for result in extraction.get("ocr_results") or [])
    transcript = extraction.get("transcript") or {}
    parts.append(transcript.get("text", "") if isinstance(transcript, dict) else str(transcript))
    if extraction.get("hashtags"):
        parts.append(" ".join(extraction["hashtags"]))
    return " ".join(part for part in parts if part).strip()


def _process_link(url: str, source_creator: str | None, user_id: str) -> dict:
    if not url.strip():
        raise HTTPException(422, "Link is required")
    extraction = run_extraction(url)
    classified = classify_extraction(extraction)
    combined_text = _combined_text(extraction)
    extracted = heuristic_extract(combined_text)
    _llm_extract(extracted, combined_text)
    # The classifier's category and date confidence always win over the LLM's.
    extracted["category"] = classified.primary_category
    extracted["category_confidence"] = classified.overall_confidence
    _apply_classified_dates(extracted, classified)
    extracted["source_url"] = url
    if source_creator:
        extracted["source_creator"] = source_creator if source_creator.startswith("@") else f"@{source_creator}"
    return _finalize(extracted, combined_text, user_id)


@app.get("/api/health")
def health():
    return {"status": "ok", "memory": memory_mode, "inference": inference_mode, "draft_only": True}


def _reflect(user_id: str) -> dict:
    try:
        remote = memory_provider.reflect(user_id)
    except Exception:
        remote = None
        logger.warning("Hindsight reflect failed for user_id=%s; falling back to local weekly_reflect", user_id, exc_info=True)
    if remote:
        return remote
    return weekly_reflect([a for a in seed["actions"] if a["user_id"] == user_id], opportunities)


def _confirmation(action_result: dict | None) -> list[dict]:
    """Human-readable outcome of an accept: what was created and where (with
    a link when a real provider produced one; "mock" when keys are missing)."""
    if not action_result:
        return []
    items = []
    if action_result.get("calendar_event_id"):
        mock = calendar_mode != "google-calendar"
        items.append({"kind": "calendar", "mock": mock, "url": action_result.get("calendar_url"),
                      "label": "Added to calendar (mock — no Google keys set)" if mock else "Added to Google Calendar"})
    elif action_result.get("kind") == "note_only":
        items.append({"kind": "calendar", "mock": False, "url": None, "label": "No calendar event — deadline not confirmed"})
    if action_result.get("notion_page_id"):
        mock = notes_mode != "notion"
        items.append({"kind": "notes", "mock": mock, "url": action_result.get("notion_url"),
                      "label": "Note saved (mock — no Notion keys set)" if mock else "Notion page created"})
    return items


@app.get("/api/bootstrap")
def bootstrap(x_user_id: str | None = Header(default=None)):
    user_id = _user(x_user_id)
    return {
        "user": seed["demo_user"],
        "memories": seed.get("memories", []),
        "demo_seed": demo_seed_enabled(),
        "opportunities": sorted(opportunities, key=lambda item: item.get("rank", 0), reverse=True),
        "sources": sources,
        "reflect": _reflect(user_id),
        "modes": {
            "memory": memory_mode, "source_trust": source_trust_mode, "inference": inference_mode,
            "transcription": "whisper" if os.getenv("ENABLE_LOCAL_WHISPER") == "true" else "demo",
        },
    }


@app.post("/api/process-caption")
def process_caption(payload: CaptionInput, x_user_id: str | None = Header(default=None)):
    return _process(payload.caption, payload.source_creator, _user(x_user_id))


@app.post("/api/process-upload")
async def process_upload(
    file: UploadFile = File(...), caption: str = Form(default=""),
    source_creator: str = Form(default=""), x_user_id: str | None = Header(default=None),
):
    transcript = caption
    transcription_mode = "caption-fallback"
    if os.getenv("ENABLE_LOCAL_WHISPER") == "true":
        suffix = Path(file.filename or "upload.mp4").suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            temp.write(await file.read())
            temp_path = temp.name
        try:
            sys.path.insert(0, str(BACKEND_DIR / "extraction" / "audio"))
            from transcription import transcribe_audio
            transcript = transcribe_audio(temp_path)["text"]
            transcription_mode = "whisper"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    if not transcript:
        transcript = "Remote React developer hiring at Demo Company. 1-2 years experience. Apply by 12 October."
        transcription_mode = "demo-transcript"
    result = _process(transcript, source_creator, _user(x_user_id))
    result.update({"uploaded_filename": file.filename, "transcription_mode": transcription_mode})
    return result


@app.post("/api/process-link")
def process_link(payload: LinkInput, x_user_id: str | None = Header(default=None)):
    try:
        return _process_link(payload.url, payload.source_creator, _user(x_user_id))
    except LinkFetchFailed as exc:
        raise HTTPException(422, {"error_type": "AutoFetchFailed", "message": str(exc)})


def _source_trust_kind(action: str, reason: str | None) -> str:
    reason_lower = (reason or "").lower()
    if "fake" in reason_lower:
        return "rejected_as_fake"
    if "dead" in reason_lower or "expired" in reason_lower:
        return "dead_link"
    if action == "accepted":
        return "confirmed"
    return "neutral"


@app.post("/api/opportunities/{opportunity_id}/action")
def record_action(opportunity_id: str, payload: ActionInput, x_user_id: str | None = Header(default=None)):
    if payload.action not in {"saved", "accepted", "rejected", "skipped"}:
        raise HTTPException(422, "Action must be saved, accepted, rejected, or skipped")
    opportunity = next((item for item in opportunities if item["id"] == opportunity_id), None)
    if not opportunity:
        raise HTTPException(404, "Opportunity not found")
    opportunity["status"] = payload.action
    action_result = None
    if payload.action == "accepted":
        action_result = accept_opportunity(opportunity, opportunities, calendar_provider, notes_provider)
    user_id = _user(x_user_id)
    event = {"opportunity_id": opportunity_id, "user_id": user_id, "action": payload.action, "reason": payload.reason}
    seed["actions"].append(event)
    decision_text = f"{payload.action.title()} {opportunity['title']} at {opportunity['company']}. Reason: {payload.reason or 'not provided'}"
    decision_metadata = {"kind": "decision", "action": payload.action, **_opportunity_memory_metadata(opportunity_id, opportunity)}
    try:
        memory = memory_provider.remember(user_id, decision_text, decision_metadata)
    except Exception:
        logger.warning("Hindsight retain failed for user_id=%s on decision; falling back to demo memory", user_id, exc_info=True)
        memory = DemoMemoryProvider().remember(user_id, decision_text, decision_metadata)
    try:
        safe_reason, _ = redact_for_memory(payload.reason or "not provided")
        source_trust_provider.remember(
            opportunity.get("source_creator"),
            f"{payload.action.title()}: {opportunity['title']} at {opportunity['company']}. Reason: {safe_reason}",
            {"kind": _source_trust_kind(payload.action, payload.reason), "opportunity_id": opportunity_id},
        )
    except Exception:
        logger.warning("Source-trust retain failed for source_creator=%s", opportunity.get("source_creator"), exc_info=True)
    return {"ok": True, "status": payload.action, "memory_redactions": memory.get("redactions", []), "action_result": action_result, "confirmation": _confirmation(action_result)}


@app.get("/api/reflect")
def reflect(x_user_id: str | None = Header(default=None)):
    return _reflect(_user(x_user_id))
