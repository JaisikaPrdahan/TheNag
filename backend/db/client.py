"""
Shared Postgres connection, used by all three backend subsystems
(extraction, classification, actions) -- per docs/database-schema.md
("Where this lives in the codebase"). Each subsystem imports this
rather than opening its own connection independently.

This file didn't exist yet anywhere in the repo; it's created here
because backend/classification/db_writes.py needs it to fulfil
Person 2's documented responsibility of creating the `opportunities`
row and updating `reels`/`stage_events`. Person 1 and Person 3 should
import from here too rather than duplicating connection setup.
"""

import os

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """
    Returns a new psycopg2 connection using DATABASE_URL from the
    environment (see .env.example / docker-compose.yml at the repo
    root). Raises KeyError with a clear message if DATABASE_URL isn't
    set, rather than a confusing psycopg2 error.
    """
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env, "
            "run `docker compose up -d` to start Postgres, and make "
            "sure your process loads .env (e.g. via python-dotenv)."
        )

    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
