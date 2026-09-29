# Actions subsystem

Turns an accepted opportunity into draft-only external artifacts: a calendar
event for green-confidence dates, and a note/page everywhere else.

## Interface

- `providers.py` -- `CalendarProvider` / `NotesProvider` ABCs. `build_calendar_provider()` /
  `build_notes_provider()` return the real provider when credentials are present
  (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REFRESH_TOKEN` for Google Calendar,
  `NOTION_API_KEY`/`NOTION_DATABASE_ID` for Notion), otherwise an in-memory mock --
  same pattern as `backend/memory/providers.py`.
- `engine.py` -- `accept_opportunity(opportunity, ...)` is the integration point,
  called from `backend/api/app.py`'s `record_action()` when `action == "accepted"`.
  Green-confidence dates get a calendar event; yellow dates, an uncertain category,
  or a duplicate of an opportunity that isn't already accepted get a note only
  (marked "needs confirmation" where relevant). A duplicate of an already-accepted
  opportunity updates the existing calendar event and appends a change-log line to
  its note instead of creating new artifacts.

## Auth

Google: refresh-token flow only (`GOOGLE_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN`), token
refreshed via a raw `urllib` POST to `https://oauth2.googleapis.com/token` -- no
google-auth SDK. Get a refresh token via the
[OAuth 2.0 Playground](https://developers.google.com/oauthplayground) with the
`https://www.googleapis.com/auth/calendar` scope (use your own client ID/secret
under the gear icon, not the Playground's shared ones).

Notion: `NOTION_API_KEY` (an internal integration token) + `NOTION_DATABASE_ID`
(the target database, shared with that integration).

Both are optional; omitting either falls back to its mock provider.
