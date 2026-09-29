"""Memory provider boundary.

Demo mode is deterministic and in-process. HindsightCloudProvider is the single
integration point for production credentials; app data never enters this layer.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

from .privacy import redact_for_memory


def demo_seed_enabled() -> bool:
    """Seed data (backend/demo/seed.json) is loaded only when DEMO_SEED=true."""
    return os.getenv("DEMO_SEED", "false").strip().lower() == "true"


logger = logging.getLogger("thenag.hindsight")
META_PREFIX = "thenag-meta:"


class HindsightError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _hindsight_request(method: str, base_url: str, api_key: str, path: str, payload: dict) -> dict:
    """Official Hindsight HTTP API call (paths are under /v1/default/banks/...)."""
    req = request.Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "User-Agent": "TheNag/1.0",
                 "Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        logger.warning("Hindsight %s %s -> HTTP %s: %s", method, path, exc.code, body)
        raise HindsightError(f"Hindsight Cloud request failed: HTTP {exc.code}: {body}", exc.code) from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HindsightError(f"Hindsight Cloud request failed: {exc}") from exc


def _bank_path(bank_id: str, suffix: str = "") -> str:
    return f"v1/default/banks/{parse.quote(bank_id, safe='')}{suffix}"


def _hindsight_retain(base_url: str, api_key: str, bank_id: str, content: str, metadata: dict) -> dict:
    # The API has no free-form metadata field, so ours rides in `context` (JSON) and is
    # parsed back on recall; `kind` also becomes a tag.
    item = {"content": content, "context": META_PREFIX + json.dumps(metadata, default=str),
            "timestamp": datetime.now(timezone.utc).isoformat()}
    if metadata.get("kind"):
        item["tags"] = [str(metadata["kind"])]
    path = _bank_path(bank_id, "/memories")
    try:
        return _hindsight_request("POST", base_url, api_key, path, {"items": [item]})
    except HindsightError as exc:
        if exc.status != 404:
            raise
        _hindsight_request("PUT", base_url, api_key, _bank_path(bank_id), {})  # bank doesn't exist yet
        return _hindsight_request("POST", base_url, api_key, path, {"items": [item]})


def _hindsight_recall(base_url: str, api_key: str, bank_id: str, query: str) -> list[dict]:
    try:
        result = _hindsight_request("POST", base_url, api_key, _bank_path(bank_id, "/memories/recall"), {"query": query or " "})
    except HindsightError as exc:
        if exc.status == 404:
            return []  # no bank yet == no memories
        raise
    memories = []
    for item in result.get("results", []):
        context = item.get("context") or ""
        metadata = {}
        if context.startswith(META_PREFIX):
            try:
                metadata = json.loads(context[len(META_PREFIX):])
            except ValueError:
                pass
        memories.append({"id": item.get("id"), "text": item.get("text", ""), "type": item.get("type"), "metadata": metadata})
    return memories


class MemoryProvider(ABC):
    @abstractmethod
    def recall(self, user_id: str, query: str) -> list[dict]: ...

    @abstractmethod
    def remember(self, user_id: str, text: str, metadata: dict) -> dict: ...

    def reflect(self, user_id: str) -> dict | None:
        """A Hindsight-computed weekly reflection. None means "use the
        caller's local fallback math" -- the default, and DemoMemoryProvider's
        behavior, since there's nothing remote to compute it from."""
        return None


class DemoMemoryProvider(MemoryProvider):
    def __init__(self, seed_path: str | Path | None = None):
        path = Path(seed_path) if seed_path else Path(__file__).parents[1] / "demo" / "seed.json"
        load_seed = bool(seed_path) or demo_seed_enabled()
        seed = json.loads(path.read_text(encoding="utf-8")) if load_seed and path.exists() else {}
        self.memories = seed.get("memories", [])
        self.actions = seed.get("actions", [])

    def recall(self, user_id: str, query: str) -> list[dict]:
        terms = set(query.lower().split())
        matches = []
        for memory in self.memories:
            if memory.get("user_id") != user_id:
                continue
            haystack = f"{memory.get('text', '')} {json.dumps(memory.get('metadata', {}))}".lower()
            score = sum(term in haystack for term in terms)
            if score or memory.get("metadata", {}).get("kind") == "preference":
                matches.append({**memory, "relevance": score})
        return sorted(matches, key=lambda item: item.get("relevance", 0), reverse=True)[:8]

    def remember(self, user_id: str, text: str, metadata: dict) -> dict:
        safe_text, redactions = redact_for_memory(text)
        record = {
            "id": f"memory-{len(self.memories) + 1}",
            "user_id": user_id,
            "text": safe_text,
            "metadata": metadata,
            "redactions": redactions,
        }
        self.memories.append(record)
        return record


class HindsightCloudProvider(MemoryProvider):
    """Small HTTP adapter for a configured Hindsight Cloud deployment.

    Endpoint paths can be overridden because hosted Hindsight deployments may
    expose different gateways. Failures are surfaced to the caller, which then
    switches to demo mode instead of breaking the application.
    """

    def __init__(self):
        self.base_url = os.environ["HINDSIGHT_API_URL"].rstrip("/")
        self.api_key = os.environ["HINDSIGHT_API_KEY"]
        self.bank_prefix = os.getenv("HINDSIGHT_BANK_PREFIX", "thenag-user")

    def _bank(self, user_id: str) -> str:
        return f"{self.bank_prefix}-{user_id}"

    def recall(self, user_id: str, query: str) -> list[dict]:
        return _hindsight_recall(self.base_url, self.api_key, self._bank(user_id), query)

    def remember(self, user_id: str, text: str, metadata: dict) -> dict:
        safe_text, redactions = redact_for_memory(text)
        result = _hindsight_retain(self.base_url, self.api_key, self._bank(user_id), safe_text,
                                   {**metadata, "memory_defense_redactions": redactions})
        return {**result, "redactions": redactions}

    def reflect(self, user_id: str) -> dict | None:
        try:
            result = _hindsight_request(
                "POST", self.base_url, self.api_key, _bank_path(self._bank(user_id), "/reflect"),
                {"query": "In two sentences, what patterns show in what this user saves, accepts and skips?", "budget": "low"},
            )
        except HindsightError:
            return None
        return {"text": result["text"]} if result.get("text") else None


def build_memory_provider() -> tuple[MemoryProvider, str]:
    if os.getenv("HINDSIGHT_API_KEY") and os.getenv("HINDSIGHT_API_URL"):
        return HindsightCloudProvider(), "hindsight-cloud"
    return DemoMemoryProvider(), "demo-memory"


class SourceTrustProvider(ABC):
    """Shared, aggregate evidence about a source (a creator/account), never a
    user's private preferences or decisions -- kept as its own bank so it can
    never be confused with (or leak into) anyone's private memory bank."""

    @abstractmethod
    def recall(self, source_creator: str) -> list[dict]: ...

    @abstractmethod
    def remember(self, source_creator: str, text: str, metadata: dict) -> dict: ...


class DemoSourceTrustProvider(SourceTrustProvider):
    def __init__(self):
        self.facts: list[dict] = []

    def recall(self, source_creator: str) -> list[dict]:
        return [fact for fact in self.facts if fact.get("source_creator") == source_creator]

    def remember(self, source_creator: str, text: str, metadata: dict) -> dict:
        record = {"id": f"source-fact-{len(self.facts) + 1}", "source_creator": source_creator, "text": text, "metadata": metadata}
        self.facts.append(record)
        return record


class HindsightSourceTrustProvider(SourceTrustProvider):
    """Same Hindsight deployment as HindsightCloudProvider, but a single
    fixed, non-per-user bank -- shared aggregate evidence about sources,
    structurally separate from any user's private bank."""

    BANK_ID = "source-trust"

    def __init__(self):
        self.base_url = os.environ["HINDSIGHT_API_URL"].rstrip("/")
        self.api_key = os.environ["HINDSIGHT_API_KEY"]

    def recall(self, source_creator: str) -> list[dict]:
        return _hindsight_recall(self.base_url, self.api_key, self.BANK_ID, source_creator or "")

    def remember(self, source_creator: str, text: str, metadata: dict) -> dict:
        return _hindsight_retain(self.base_url, self.api_key, self.BANK_ID, text, {**metadata, "source_creator": source_creator})


def build_source_trust_provider() -> tuple[SourceTrustProvider, str]:
    if os.getenv("HINDSIGHT_API_KEY") and os.getenv("HINDSIGHT_API_URL"):
        return HindsightSourceTrustProvider(), "hindsight-source-trust"
    return DemoSourceTrustProvider(), "demo-source-trust"
