"""Draft-only action provider boundary: calendar events and notes/pages.

Mock providers are used when credentials are missing, so the product
walkthrough never breaks on a missing integration -- same pattern as
backend/memory/providers.py and backend/pipeline/providers.py. Real
providers are raw urllib HTTP adapters; no Google/Notion SDK dependency.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from urllib import error, parse, request


class CalendarProvider(ABC):
    @abstractmethod
    def create_event(self, summary: str, description: str, start_date: str) -> dict: ...

    @abstractmethod
    def update_event(self, event_id: str, summary: str, description: str, start_date: str) -> dict: ...


class NotesProvider(ABC):
    @abstractmethod
    def create_note(self, title: str, body: str, status: str) -> dict: ...

    @abstractmethod
    def append_change_log(self, page_id: str, line: str) -> dict: ...


class MockCalendarProvider(CalendarProvider):
    def __init__(self):
        self._events: dict[str, dict] = {}

    def create_event(self, summary, description, start_date):
        event_id = f"mock-event-{len(self._events) + 1}"
        self._events[event_id] = {"id": event_id, "summary": summary, "description": description, "start_date": start_date}
        return self._events[event_id]

    def update_event(self, event_id, summary, description, start_date):
        event = self._events.setdefault(event_id, {"id": event_id})
        event.update({"summary": summary, "description": description, "start_date": start_date})
        return event


class MockNotesProvider(NotesProvider):
    def __init__(self):
        self._notes: dict[str, dict] = {}

    def create_note(self, title, body, status):
        page_id = f"mock-note-{len(self._notes) + 1}"
        self._notes[page_id] = {"id": page_id, "title": title, "body": body, "status": status, "change_log": []}
        return self._notes[page_id]

    def append_change_log(self, page_id, line):
        note = self._notes.setdefault(page_id, {"id": page_id, "change_log": []})
        note["change_log"].append(line)
        return note


class GoogleCalendarProvider(CalendarProvider):
    """Refresh-token-only Google Calendar adapter.

    Needs GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN.
    The access token is refreshed via a plain urllib POST (no google-auth
    dependency); Google access tokens are short-lived (~1hr) so it's
    refreshed per-process-lifetime rather than persisted.
    """

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    def __init__(self):
        self.client_id = os.environ["GOOGLE_CLIENT_ID"]
        self.client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
        self.refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]
        self._access_token: str | None = None
        self._access_token_expiry = 0.0

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expiry:
            return self._access_token
        payload = parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")
        req = request.Request(self.TOKEN_URL, data=payload, method="POST")
        try:
            with request.urlopen(req, timeout=12) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Google token refresh failed: {exc}") from exc
        self._access_token = body["access_token"]
        self._access_token_expiry = time.time() + body.get("expires_in", 3600) - 60
        return self._access_token

    def _request(self, method: str, url: str, payload: dict | None = None) -> dict:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Authorization": f"Bearer {self._get_access_token()}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Google Calendar request failed: {exc}") from exc

    def create_event(self, summary, description, start_date):
        body = self._request("POST", self.EVENTS_URL, {
            "summary": summary, "description": description,
            "start": {"date": start_date}, "end": {"date": start_date},
        })
        return {"id": body["id"], "summary": summary, "description": description, "start_date": start_date, "url": body.get("htmlLink")}

    def update_event(self, event_id, summary, description, start_date):
        body = self._request("PATCH", f"{self.EVENTS_URL}/{event_id}", {
            "summary": summary, "description": description,
            "start": {"date": start_date}, "end": {"date": start_date},
        })
        return {"id": body["id"], "summary": summary, "description": description, "start_date": start_date}


class NotionProvider(NotesProvider):
    """Notion adapter. Needs NOTION_API_KEY and NOTION_DATABASE_ID."""

    API_URL = "https://api.notion.com/v1"
    VERSION = "2022-06-28"

    def __init__(self):
        self.api_key = os.environ["NOTION_API_KEY"]
        self.database_id = os.environ["NOTION_DATABASE_ID"]

    def _request(self, method: str, path: str, payload: dict) -> dict:
        req = request.Request(
            f"{self.API_URL}/{path.lstrip('/')}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Notion-Version": self.VERSION,
            },
            method=method,
        )
        try:
            with request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Notion request failed: {exc}") from exc

    def create_note(self, title, body, status):
        page = self._request("POST", "pages", {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Name": {"title": [{"text": {"content": title}}]},
                "Status": {"select": {"name": status}},
            },
            "children": [{
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": body}}]},
            }],
        })
        return {"id": page["id"], "title": title, "body": body, "status": status, "change_log": [], "url": page.get("url")}

    def append_change_log(self, page_id, line):
        self._request("PATCH", f"blocks/{page_id}/children", {
            "children": [{
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": f"Change log: {line}"}}]},
            }],
        })
        return {"id": page_id, "change_log_appended": line}


def build_calendar_provider() -> tuple[CalendarProvider, str]:
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REFRESH_TOKEN"):
        return GoogleCalendarProvider(), "google-calendar"
    return MockCalendarProvider(), "mock-calendar"


def build_notes_provider() -> tuple[NotesProvider, str]:
    if os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID"):
        return NotionProvider(), "notion"
    return MockNotesProvider(), "mock-notes"
