# TheNag data boundary

## PostgreSQL application data

| Table | Responsibility |
| --- | --- |
| `reels` | Input record and processing stage |
| `stage_events` | Append-only pipeline audit log |
| `opportunities` | Structured listing, extraction/source confidence, rank, duplicate state, change history, and draft recommendation |
| `opportunity_actions` | User decision event (`saved`, `accepted`, `rejected`, `skipped`, `viewed`) |
| `sources` | Shared, evidence-backed source reliability aggregates |
| `notification_preferences` | Per-opportunity notification settings |

Migration `005_memory_first.sql` adds opportunity detail, ranking, duplicate, action, and source-trust fields. It replaces the legacy category constraint with `jobs_gigs`, `interviews_hiring_drives`, and `uncertain`.

Migration `006_action_provider_ids.sql` adds `notion_page_id`, tracked the same way `calendar_event_id` (added in `003_opportunities.sql`) tracks the calendar artifact created on accept. A re-confirmed duplicate's change-log entries live inside the existing `notes` jsonb column rather than their own column.

## Hindsight private memory

Each user receives a separate bank named from `HINDSIGHT_BANK_PREFIX` plus their user id. The bank can retain preferences, inferred patterns, and redacted decision summaries. It must not store contact information and must not be queried across users.

```text
User decision → redact email/phone → user-specific Hindsight bank
Source verification → aggregate evidence → PostgreSQL sources table
```

The shared `sources` table is intentionally separate from personal memory. It can support a verified-opportunity B2B feed without exposing any individual history.
