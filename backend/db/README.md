# backend/db — shared Postgres connection + migrations

Shared by all three backend subsystems (`extraction/`, `classification/`,
`actions/`). See `docs/database-schema.md` for the full table
reference and who-writes-what. This folder didn't exist before this
change; it was added because `backend/classification/db_writes.py`
needs `get_connection()` and the `opportunities`/`reels`/`stage_events`
tables to actually exist.

## What's here

- `client.py` — `get_connection()`, a thin wrapper around `psycopg2`
  reading `DATABASE_URL` from the environment.
- `migrations/*.sql` — one file per table (`reels`, `stage_events`,
  `opportunities`, `notification_preferences`), run automatically by
  Postgres on first container start (see the repo-root
  `docker-compose.yml`, which mounts this folder at
  `/docker-entrypoint-initdb.d`).

## Running the database locally

From the repo root:

```
docker compose up -d
```

This starts Postgres and runs every `.sql` file in `migrations/` once,
in filename order (hence the `00N_` prefixes). To wipe and re-run them
after a schema change during development:

```
docker compose down -v
docker compose up -d
```

`-v` deletes the data volume too — local dev only.

## Environment

Copy `.env.example` (repo root) to `.env` and make sure your process
loads it (e.g. `python-dotenv`, or your framework's own env loading).
`DATABASE_URL` for local dev is:

```
postgresql://thenag:thenag_dev@localhost:5432/thenag
```
