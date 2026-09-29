"""Retains backend/demo/seed.json's history into the real Hindsight banks
(per-user private memory + the shared source-trust bank) so a fresh Hindsight
deployment starts with the same history the in-process demo mode has always
shown, instead of an empty bank.

Idempotent: each retained fact carries a `seed_id` in its metadata, and the
script recalls that exact id before retaining -- running it twice does not
duplicate facts. Safe to run without HINDSIGHT_API_URL/HINDSIGHT_API_KEY set
(falls back to the in-process demo providers, which is a no-op after the
process exits, but lets you dry-run the script's logic).

Usage (from backend/api's venv, which already has everything this needs --
this script's own dependencies are stdlib-only, see backend/memory/providers.py):
    cd backend/demo
    ..\api\venv\Scripts\python.exe seed_hindsight.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from memory import build_memory_provider, build_source_trust_provider, redact_for_memory  # noqa: E402

SEED_PATH = Path(__file__).resolve().parent / "seed.json"


def _already_seeded(recall_fn, query: str, seed_id: str) -> bool:
    try:
        hits = recall_fn(query)
    except Exception:
        return False
    return any(seed_id in json.dumps(hit) for hit in hits)


def _seed_memories(memory_provider, seed: dict) -> int:
    count = 0
    for index, memory in enumerate(seed.get("memories", [])):
        seed_id = f"seed-memory-{index}"
        user_id = memory["user_id"]
        if _already_seeded(lambda q, u=user_id: memory_provider.recall(u, q), seed_id, seed_id):
            continue
        memory_provider.remember(user_id, memory["text"], {**memory.get("metadata", {}), "seed_id": seed_id})
        count += 1
    return count


def _seed_actions(memory_provider, source_trust_provider, seed: dict) -> tuple[int, int]:
    opportunities_by_id = {opp["id"]: opp for opp in seed.get("opportunities", [])}
    decision_count = 0
    source_fact_count = 0
    for index, action in enumerate(seed.get("actions", [])):
        seed_id = f"seed-action-{index}"
        user_id = action["user_id"]
        opportunity = opportunities_by_id.get(action["opportunity_id"], {})
        title, company = opportunity.get("title", "Unknown role"), opportunity.get("company", "Unknown company")
        source_creator = opportunity.get("source_creator")

        if not _already_seeded(lambda q, u=user_id: memory_provider.recall(u, q), seed_id, seed_id):
            text = f"{action['action'].title()} {title} at {company}."
            metadata = {
                "kind": "decision", "action": action["action"], "seed_id": seed_id,
                "occurred_at": action.get("created_at"), "opportunity_id": action["opportunity_id"],
                "title": title, "company": company, "deadline": opportunity.get("deadline"),
                "source_creator": source_creator,
            }
            memory_provider.remember(user_id, text, metadata)
            decision_count += 1

        if source_creator and not _already_seeded(lambda q: source_trust_provider.recall(source_creator), seed_id, seed_id):
            kind = "confirmed" if action["action"] == "accepted" else "neutral"
            source_trust_provider.remember(
                source_creator, f"{action['action'].title()}: {title} at {company}.",
                {"kind": kind, "seed_id": seed_id, "occurred_at": action.get("created_at"), "opportunity_id": action["opportunity_id"]},
            )
            source_fact_count += 1
    return decision_count, source_fact_count


def _seed_sources(source_trust_provider, seed: dict) -> int:
    count = 0
    for source in seed.get("sources", []):
        seed_id = f"seed-source-{source['id']}"
        source_creator = source["name"]
        if _already_seeded(lambda q: source_trust_provider.recall(source_creator), seed_id, seed_id):
            continue
        safe_evidence, _ = redact_for_memory(source.get("evidence", ""))
        text = (
            f"{source_creator}: trust_score={source['trust_score']}, "
            f"confirmed={source.get('confirmed', 0)}, misleading={source.get('misleading', 0)}, "
            f"changed={source.get('changed', 0)}. {safe_evidence}"
        )
        source_trust_provider.remember(source_creator, text, {"kind": "aggregate_summary", "seed_id": seed_id})
        count += 1
    return count


def main() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    memory_provider, memory_mode = build_memory_provider()
    source_trust_provider, source_trust_mode = build_source_trust_provider()
    print(f"Seeding into memory={memory_mode}, source_trust={source_trust_mode}")
    if memory_mode == "demo-memory":
        print("HINDSIGHT_API_URL/HINDSIGHT_API_KEY not set -- seeding the in-process demo providers only (lost on exit).")

    memories_retained = _seed_memories(memory_provider, seed)
    decisions_retained, source_facts_from_actions = _seed_actions(memory_provider, source_trust_provider, seed)
    source_summaries_retained = _seed_sources(source_trust_provider, seed)

    print(f"Retained {memories_retained} preference memories, {decisions_retained} decisions, "
          f"{source_facts_from_actions + source_summaries_retained} source-trust facts "
          f"({source_facts_from_actions} from actions, {source_summaries_retained} aggregate summaries).")
    print("Re-run this script any time -- already-retained facts (matched by seed_id) are skipped.")


if __name__ == "__main__":
    main()
