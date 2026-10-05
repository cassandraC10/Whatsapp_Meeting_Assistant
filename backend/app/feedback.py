from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.cloud import (
    cloud_database_connection,
    load_cloud_config,
)
from backend.app.event_store import (
    initialize_event_store,
    record_product_event,
)
from backend.app.models import (
    FeedbackRating,
    FeedbackResponse,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_DATABASE_PATH = BACKEND_ROOT / "data" / "tca_auth.db"
FEEDBACK_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(FEEDBACK_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_feedback_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_feedback (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                call_id TEXT NOT NULL,
                rating TEXT NOT NULL CHECK (rating IN ('helpful', 'needs_work')),
                comment TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, call_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_user_updated
            ON conversation_feedback(user_id, updated_at DESC)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_feedback_call
            ON conversation_feedback(call_id)
            """
        )

        connection.commit()

    initialize_event_store()


def _row_to_response(row: sqlite3.Row) -> FeedbackResponse:
    return FeedbackResponse(
        id=row["id"],
        call_id=row["call_id"],
        rating=FeedbackRating(row["rating"]),
        comment=row["comment"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def get_feedback(
    *,
    user_id: str,
    call_id: str,
) -> FeedbackResponse | None:
    initialize_feedback_store()

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                call_id,
                rating,
                comment,
                created_at,
                updated_at
            FROM conversation_feedback
            WHERE user_id = ? AND call_id = ?
            """,
            (user_id, call_id),
        ).fetchone()

    if row is None:
        return None

    return _row_to_response(row)


def submit_feedback(
    *,
    user_id: str,
    call_id: str,
    rating: FeedbackRating,
    comment: str | None,
) -> FeedbackResponse:
    initialize_feedback_store()

    clean_comment = " ".join((comment or "").strip().split())

    if len(clean_comment) > 2000:
        raise ValueError("Feedback must be 2000 characters or fewer.")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    with _connect() as connection:
        existing = connection.execute(
            """
            SELECT
                id,
                rating,
                comment,
                created_at,
                updated_at
            FROM conversation_feedback
            WHERE user_id = ? AND call_id = ?
            """,
            (user_id, call_id),
        ).fetchone()

        if existing is None:
            feedback_id = str(uuid4())

            connection.execute(
                """
                INSERT INTO conversation_feedback (
                    id,
                    user_id,
                    call_id,
                    rating,
                    comment,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    user_id,
                    call_id,
                    rating.value,
                    clean_comment or None,
                    now_iso,
                    now_iso,
                ),
            )

            event_name = "feedback_submitted"
            event_properties = {
                "rating": rating.value,
                "has_comment": bool(clean_comment),
                "feedback_id": feedback_id,
                "is_update": False,
            }

        else:
            feedback_id = str(existing["id"])
            old_rating = str(existing["rating"])
            old_comment = existing["comment"] or ""

            if (
                old_rating == rating.value
                and old_comment == clean_comment
            ):
                return FeedbackResponse(
                    id=feedback_id,
                    call_id=call_id,
                    rating=FeedbackRating(old_rating),
                    comment=old_comment or None,
                    created_at=datetime.fromisoformat(
                        existing["created_at"]
                    ),
                    updated_at=datetime.fromisoformat(
                        existing["updated_at"]
                    ),
                )

            connection.execute(
                """
                UPDATE conversation_feedback
                SET
                    rating = ?,
                    comment = ?,
                    updated_at = ?
                WHERE user_id = ? AND call_id = ?
                """,
                (
                    rating.value,
                    clean_comment or None,
                    now_iso,
                    user_id,
                    call_id,
                ),
            )

            event_name = "feedback_updated"
            event_properties = {
                "rating": rating.value,
                "has_comment": bool(clean_comment),
                "feedback_id": feedback_id,
                "is_update": True,
            }

        connection.commit()

    event_id = record_product_event(
        user_id=user_id,
        event_name=event_name,
        call_id=call_id,
        properties=event_properties,
    )

    _sync_feedback_to_cloud(
        user_id=user_id,
        call_id=call_id,
        feedback_id=feedback_id,
        rating=rating,
        comment=clean_comment or None,
        created_at=(
            existing["created_at"]
            if existing is not None
            else now_iso
        ),
        updated_at=now_iso,
    )

    _sync_event_to_cloud(
        event_id=event_id,
        user_id=user_id,
        event_name=event_name,
        call_id=call_id,
        occurred_at=now_iso,
        properties=event_properties,
    )

    result = get_feedback(
        user_id=user_id,
        call_id=call_id,
    )

    if result is None:
        raise RuntimeError("Feedback was saved but could not be read back.")

    return result


def _cloud_database_ready() -> bool:
    config = load_cloud_config()
    return config.enabled and config.database_configured


def _sync_feedback_to_cloud(
    *,
    user_id: str,
    call_id: str,
    feedback_id: str,
    rating: FeedbackRating,
    comment: str | None,
    created_at: str,
    updated_at: str,
) -> None:
    if not _cloud_database_ready():
        return

    try:
        with cloud_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tca_feedback (
                        id,
                        user_id,
                        call_id,
                        rating,
                        comment,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, call_id)
                    DO UPDATE SET
                        rating = EXCLUDED.rating,
                        comment = EXCLUDED.comment,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        feedback_id,
                        user_id,
                        call_id,
                        rating.value,
                        comment,
                        created_at,
                        updated_at,
                    ),
                )

            connection.commit()
    except Exception:
        # Local feedback remains available when cloud mirroring is degraded.
        return


def _sync_event_to_cloud(
    *,
    event_id: str,
    user_id: str,
    event_name: str,
    call_id: str,
    occurred_at: str,
    properties: dict[str, Any],
) -> None:
    if not _cloud_database_ready():
        return

    try:
        with cloud_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tca_product_events (
                        id,
                        user_id,
                        event_name,
                        call_id,
                        occurred_at,
                        properties_json,
                        source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        event_id,
                        user_id,
                        event_name,
                        call_id,
                        occurred_at,
                        json.dumps(
                            properties,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        "backend",
                    ),
                )

            connection.commit()
    except Exception:
        return
