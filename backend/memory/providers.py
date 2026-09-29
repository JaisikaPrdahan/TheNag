"""Memory provider boundary.

Demo mode is deterministic and in-process. HindsightCloudProvider is the single
integration point for production credentials; app data never enters this layer.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from urllib import error, request

from .privacy import redact_for_memory


def _hindsight_post(base_url: str, api_key: str, path: str, payload: dict) -> dict:
    req = request.Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Hindsight Cloud request failed: {exc}") from exc


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
        seed = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
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

    def _post(self, path: str, payload: dict) -> dict:
        return _hindsight_post(self.base_url, self.api_key, path, payload)

    def recall(self, user_id: str, query: str) -> list[dict]:
        result = self._post("recall", {"bank_id": f"{self.bank_prefix}-{user_id}", "query": query})
        return result.get("memories", result.get("results", []))

    def remember(self, user_id: str, text: str, metadata: dict) -> dict:
        safe_text, redactions = redact_for_memory(text)
        result = self._post(
            "retain",
            {
                "bank_id": f"{self.bank_prefix}-{user_id}",
                "content": safe_text,
                "metadata": {**metadata, "memory_defense_redactions": redactions},
            },
        )
        return {**result, "redactions": redactions}

    def reflect(self, user_id: str) -> dict | None:
        try:
            result = self._post("reflect", {"bank_id": f"{self.bank_prefix}-{user_id}"})
        except RuntimeError:
            return None
        return result or None


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
        result = _hindsight_post(self.base_url, self.api_key, "recall", {"bank_id": self.BANK_ID, "query": source_creator})
        return result.get("memories", result.get("results", []))

    def remember(self, source_creator: str, text: str, metadata: dict) -> dict:
        return _hindsight_post(
            self.base_url, self.api_key, "retain",
            {"bank_id": self.BANK_ID, "content": text, "metadata": {**metadata, "source_creator": source_creator}},
        )


def build_source_trust_provider() -> tuple[SourceTrustProvider, str]:
    if os.getenv("HINDSIGHT_API_KEY") and os.getenv("HINDSIGHT_API_URL"):
        return HindsightSourceTrustProvider(), "hindsight-source-trust"
    return DemoSourceTrustProvider(), "demo-source-trust"
