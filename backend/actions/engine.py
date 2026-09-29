"""Turns an accepted opportunity into draft-only external artifacts.

accept_opportunity() is the API's integration point (see
backend/api/app.py::record_action()). Never applies on a user's behalf --
only creates/updates a calendar event and/or a note.

Rules:
  - A duplicate of an opportunity that's already been accepted updates
    that opportunity's existing calendar event (if any) and appends a
    change-log line to its note, instead of creating new artifacts.
  - Otherwise: an "Uncertain" category, or a deadline that isn't
    green-confidence, gets a note only (no calendar event -- an
    unconfirmed date shouldn't land on the calendar). A green-confidence
    deadline gets both a calendar event and a confirmed note.
  - Opportunities with no confidence info at all (e.g. caption/upload
    input, which the classifier never touched) default to yellow --
    note only -- since their dates are unverified heuristic extraction.
"""

from __future__ import annotations

from datetime import date


def _note_body(opportunity: dict) -> str:
    return "\n".join([
        f"Category: {opportunity.get('category', 'Uncertain')}",
        f"Location: {opportunity.get('location', 'Not provided')}",
        f"Work mode: {opportunity.get('work_mode', 'Not specified')}",
        f"Compensation: {opportunity.get('compensation', 'Not provided')}",
        f"Deadline: {opportunity.get('deadline', 'Not provided')}",
        f"Application link: {opportunity.get('application_link', 'Not provided')}",
        f"Source: {opportunity.get('source_creator', 'Unknown')}",
    ])


def _find_previous(opportunity: dict, opportunities: list[dict]) -> dict | None:
    previous_id = (opportunity.get("duplicate") or {}).get("previous_id")
    if not previous_id:
        return None
    return next((item for item in opportunities if item.get("id") == previous_id), None)


def _update_existing(opportunity: dict, previous: dict, calendar_provider, notes_provider) -> dict:
    duplicate = opportunity.get("duplicate") or {}
    change_line = f"Re-confirmed via {opportunity.get('source_creator', 'unknown source')} on {date.today().isoformat()}: {duplicate.get('label', 'duplicate listing')}."
    if duplicate.get("changes"):
        change_line += " Changes: " + "; ".join(
            f"{change['field']}: {change['before']} -> {change['after']}" for change in duplicate["changes"]
        )

    if previous.get("calendar_event_id"):
        calendar_provider.update_event(
            previous["calendar_event_id"],
            f"{previous.get('title')} at {previous.get('company')}",
            _note_body(previous),
            previous.get("deadline"),
        )

    notes = previous.setdefault("notes", {"status": "confirmed", "change_log": []})
    notes.setdefault("change_log", []).append(change_line)
    if previous.get("notion_page_id"):
        notes_provider.append_change_log(previous["notion_page_id"], change_line)
    else:
        note = notes_provider.create_note(
            f"{previous.get('title')} at {previous.get('company')}", _note_body(previous), notes.get("status", "confirmed"),
        )
        previous["notion_page_id"] = note["id"]

    return {
        "kind": "duplicate_update",
        "calendar_event_id": previous.get("calendar_event_id"),
        "notion_page_id": previous.get("notion_page_id"),
        "change_log_line": change_line,
    }


def accept_opportunity(opportunity: dict, opportunities: list[dict], calendar_provider, notes_provider) -> dict:
    previous = _find_previous(opportunity, opportunities)
    if previous is not None and previous.get("status") == "accepted":
        return _update_existing(opportunity, previous, calendar_provider, notes_provider)

    category_uncertain = opportunity.get("category", "Uncertain") == "Uncertain"
    deadline = opportunity.get("deadline")
    has_deadline = bool(deadline) and deadline != "Not provided"
    date_confidence = opportunity.get("deadline_confidence", "yellow")

    if not category_uncertain and has_deadline and date_confidence == "green":
        event = calendar_provider.create_event(
            f"{opportunity.get('title')} at {opportunity.get('company')}", _note_body(opportunity), deadline,
        )
        opportunity["calendar_event_id"] = event["id"]
        note = notes_provider.create_note(
            f"{opportunity.get('title')} at {opportunity.get('company')}", _note_body(opportunity), "confirmed",
        )
        opportunity["notion_page_id"] = note["id"]
        opportunity["notes"] = {"status": "confirmed", "change_log": []}
        return {"kind": "calendar_event", "calendar_event_id": event["id"], "notion_page_id": note["id"],
                "calendar_url": event.get("url"), "notion_url": note.get("url")}

    status = "uncertain category" if category_uncertain else ("needs confirmation" if has_deadline else "note only")
    note = notes_provider.create_note(
        f"{opportunity.get('title')} at {opportunity.get('company')}", _note_body(opportunity), status,
    )
    opportunity["notion_page_id"] = note["id"]
    opportunity["notes"] = {"status": status, "change_log": []}
    return {"kind": "note_only", "notion_page_id": note["id"], "notion_url": note.get("url"), "status": status}
