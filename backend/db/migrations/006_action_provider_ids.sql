-- notion_page_id tracks the notes/page artifact created on accept, the same
-- way calendar_event_id (added in 003) tracks the calendar artifact.
-- Change-log entries for a re-confirmed duplicate live inside the existing
-- `notes` jsonb column rather than their own column.

alter table opportunities
  add column if not exists notion_page_id text;
