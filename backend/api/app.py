"""TheNag HTTP API.

The API defaults to deterministic demo mode. Real providers are selected only
when their credentials are present, so a missing integration never breaks the
product walkthrough.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Resolve first: test runners can import this module through a path containing
# ``tests/..`` and a purely lexical ``parents`` lookup would otherwise point
# at the test directory instead of the backend directory.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from memory import DemoMemoryProvider, build_memory_provider  # noqa: E402
from pipeline import duplicate_status, heuristic_extract, rank_and_explain, weekly_reflect  # noqa: E402
from pipeline.providers import GroqOpportunityExtractor  # noqa: E402


SEED_PATH = BACKEND_DIR / "demo" / "seed.json"
seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
opportunities = seed["opportunities"]
sources = seed["sources"]
source_by_name = {source["name"]: source for source in sources}
memory_provider, memory_mode = build_memory_provider()
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


def _user(user_id: str | None) -> str:
    return user_id or "demo-user"


def _process(caption: str, source_creator: str | None, user_id: str) -> dict:
    if not caption.strip():
        raise HTTPException(422, "Caption text is required")
    extracted = heuristic_extract(caption)
    if os.getenv("GROQ_API_KEY"):
        try:
            extracted.update({k: v for k, v in GroqOpportunityExtractor().extract(caption).items() if v})
        except Exception:
            extracted["provider_warning"] = "Groq was unavailable; deterministic extraction was used."
    if source_creator:
        extracted["source_creator"] = source_creator if source_creator.startswith("@") else f"@{source_creator}"
    source = source_by_name.get(extracted["source_creator"], {
        "name": extracted["source_creator"], "trust_score": 60, "observation_count": 0,
        "assessment": "Not enough history", "evidence": "New source; no shared reliability history yet.",
    })
    try:
        memories = memory_provider.recall(user_id, caption)
    except Exception:
        memories = DemoMemoryProvider().recall(user_id, caption)
        extracted["memory_warning"] = "Hindsight Cloud was unavailable; demo memory was used."
    duplicate = duplicate_status(extracted, opportunities)
    rank, why, next_action = rank_and_explain(extracted, memories, source, duplicate)
    result = {
        "id": f"processed-{len(opportunities) + 1}", **extracted,
        "source_trust": source["trust_score"], "source_detail": source,
        "duplicate": duplicate, "rank": rank, "why": why,
        "recommended_action": next_action, "status": "new",
        "draft_only": True, "memory_mode": memory_mode, "inference_mode": inference_mode,
        "recalled_memories": [m.get("text", m.get("content", "Remembered preference")) for m in memories[:4]],
    }
    opportunities.insert(0, result)
    memory_provider.remember(user_id, f"Viewed {result['title']} at {result['company']}", {"kind": "viewed", "opportunity_id": result["id"]})
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "memory": memory_mode, "inference": inference_mode, "draft_only": True}


@app.get("/api/bootstrap")
def bootstrap(x_user_id: str | None = Header(default=None)):
    user_id = _user(x_user_id)
    return {
        "user": seed["demo_user"],
        "opportunities": sorted(opportunities, key=lambda item: item.get("rank", 0), reverse=True),
        "sources": sources,
        "reflect": weekly_reflect([a for a in seed["actions"] if a["user_id"] == user_id], opportunities),
        "modes": {"memory": memory_mode, "inference": inference_mode, "transcription": "whisper" if os.getenv("ENABLE_LOCAL_WHISPER") == "true" else "demo"},
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


@app.post("/api/opportunities/{opportunity_id}/action")
def record_action(opportunity_id: str, payload: ActionInput, x_user_id: str | None = Header(default=None)):
    if payload.action not in {"saved", "accepted", "rejected", "skipped"}:
        raise HTTPException(422, "Action must be saved, accepted, rejected, or skipped")
    opportunity = next((item for item in opportunities if item["id"] == opportunity_id), None)
    if not opportunity:
        raise HTTPException(404, "Opportunity not found")
    opportunity["status"] = payload.action
    user_id = _user(x_user_id)
    event = {"opportunity_id": opportunity_id, "user_id": user_id, "action": payload.action, "reason": payload.reason}
    seed["actions"].append(event)
    memory = memory_provider.remember(
        user_id,
        f"{payload.action.title()} {opportunity['title']} at {opportunity['company']}. Reason: {payload.reason or 'not provided'}",
        {"kind": "decision", "opportunity_id": opportunity_id, "action": payload.action},
    )
    return {"ok": True, "status": payload.action, "memory_redactions": memory.get("redactions", [])}


@app.get("/api/reflect")
def reflect(x_user_id: str | None = Header(default=None)):
    user_id = _user(x_user_id)
    return weekly_reflect([a for a in seed["actions"] if a["user_id"] == user_id], opportunities)
