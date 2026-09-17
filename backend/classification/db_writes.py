"""
Person 2's database responsibilities, per docs/database-schema.md
"Who uses which table":

  - read `reels` (caption_text, hashtags -- via the extraction dict,
    not directly queried here, since Person 1 hands that off in-memory
    per docs/person1&3.md)
  - create the `opportunities` row (primary_category,
    secondary_categories, extracted_facts)
  - update `reels.current_stage`: extracted -> classifying -> classified
  - insert into `stage_events` at the start and end of this stage

This module previously didn't exist -- classify_extraction() was a
pure in-memory function with no persistence at all.
"""

import json
import os
import sys

# db/ lives one level up (backend/db/), as a sibling of this
# classification/ folder, not inside it -- add backend/ to sys.path so
# `db.client` resolves regardless of the caller's working directory,
# the same pattern combine.py uses for its ocr/audio siblings.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.client import get_connection  # noqa: E402

# classifier.py's category labels ("Job", "Hackathon/Competition", ...)
# vs. the opportunities.primary_category check constraint
# (docs/database-schema.md Table 3), which uses lowercase/underscored
# values. Keep this mapping here rather than changing either side's
# own natural naming.
CATEGORY_TO_DB_VALUE = {
    "Job": "job",
    "Internship": "internship",
    "Scholarship": "scholarship",
    "College/Admission": "college_admission",
    "Interview": "interview",
    "Exam": "exam",
    "Hackathon/Competition": "hackathon_competition",
    "Uncertain": "uncertain",
}


def _category_db_value(category):
    try:
        return CATEGORY_TO_DB_VALUE[category]
    except KeyError:
        raise ValueError(
            f"Unknown category {category!r} -- add it to "
            "CATEGORY_TO_DB_VALUE in db_writes.py, and to the "
            "opportunities.primary_category check constraint in "
            "backend/db/migrations/003_opportunities.sql if it's new."
        )


def log_stage_event(reel_id, stage, status, metadata=None, conn=None):
    """
    Append-only insert into stage_events. Never call this with UPDATE
    semantics in mind -- per docs/database-schema.md, this table is
    insert-only.
    """
    owns_conn = conn is None
    conn = conn or get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into stage_events (reel_id, stage, status, metadata)
                values (%s, %s, %s, %s)
                """,
                (reel_id, stage, status, json.dumps(metadata) if metadata else None),
            )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def update_reel_stage(reel_id, stage, error_message=None, conn=None):
    """
    Moves reels.current_stage forward (or to 'failed' with a message).
    Person 2 only ever sets 'classifying', 'classified', or 'failed'
    (while classifying) -- other stages belong to Person 1/3.
    """
    owns_conn = conn is None
    conn = conn or get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update reels
                set current_stage = %s,
                    error_message = %s,
                    updated_at = now()
                where id = %s
                """,
                (stage, error_message, reel_id),
            )
        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def create_opportunity(reel_id, user_id, classified_facts, conn=None):
    """
    Inserts the `opportunities` row from a ClassifiedFacts result
    (models.ClassifiedFacts.to_opportunity_row()). Returns the new
    opportunity's id.

    Person 2 is the one who *creates* this row -- Person 3 updates it
    later (notes, calendar_event_id, verification_conflicts) but never
    inserts a new one, per docs/database-schema.md Table 3.
    """
    owns_conn = conn is None
    conn = conn or get_connection()

    row = classified_facts.to_opportunity_row()
    db_category = _category_db_value(row["primary_category"])

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into opportunities
                    (reel_id, user_id, primary_category, secondary_categories, extracted_facts)
                values (%s, %s, %s, %s, %s)
                returning id
                """,
                (
                    reel_id,
                    user_id,
                    db_category,
                    json.dumps([
                        _category_db_value(c) for c in row["secondary_categories"]
                    ]),
                    json.dumps(row["extracted_facts"]),
                ),
            )
            opportunity_id = cur.fetchone()["id"]
        if owns_conn:
            conn.commit()
        return opportunity_id
    finally:
        if owns_conn:
            conn.close()


def classify_and_persist(reel_id, user_id, extraction):
    """
    The full Person 2 pipeline step: takes Person 1's extraction
    output for one reel, classifies it, and persists everything --
    stage transitions, stage_events, and the opportunities row.

    On any failure, marks the reel 'failed' with an error_message and
    logs a 'failed' stage_event, rather than leaving the reel stuck
    silently in 'extracted' or 'classifying' forever.
    """
    # Import here (not at module top) so this module can be imported
    # and unit-tested without classifier.py's dependencies being a
    # hard requirement for callers that only need the DB helpers.
    from classifier import classify_extraction

    conn = get_connection()

    try:
        update_reel_stage(reel_id, "classifying", conn=conn)
        log_stage_event(reel_id, "classifying", "started", conn=conn)

        classified = classify_extraction(extraction)

        opportunity_id = create_opportunity(reel_id, user_id, classified, conn=conn)

        update_reel_stage(reel_id, "classified", conn=conn)
        log_stage_event(
            reel_id,
            "classifying",
            "completed",
            metadata={
                "primary_category": classified.primary_category,
                "overall_confidence": classified.overall_confidence,
            },
            conn=conn,
        )

        conn.commit()
        return opportunity_id

    except Exception as exc:
        conn.rollback()
        update_reel_stage(reel_id, "failed", error_message=str(exc), conn=conn)
        log_stage_event(
            reel_id,
            "classifying",
            "failed",
            metadata={"error": str(exc)},
            conn=conn,
        )
        conn.commit()
        raise

    finally:
        conn.close()
