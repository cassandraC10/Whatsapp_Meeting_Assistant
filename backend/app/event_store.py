from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parent.parent
EVENTS_DATABASE_PATH = BACKEND_ROOT / "data" / "tca_auth.db"
EVENTS_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(EVENTS_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_event_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                call_id TEXT,
                occurred_at TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT 'backend'
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_events_user_time
            ON product_events(user_id, occurred_at DESC)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_events_name_time
            ON product_events(event_name, occurred_at DESC)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_product_events_call
            ON product_events(call_id)
            """
        )

        connection.commit()


def record_product_event(
    *,
    user_id: str,
    event_name: str,
    call_id: str | None = None,
    properties: dict[str, Any] | None = None,
    source: str = "backend",
) -> str:
    clean_event_name = event_name.strip()

    if not clean_event_name:
        raise ValueError("Event name cannot be empty.")

    if len(clean_event_name) > 120:
        raise ValueError("Event name is too long.")

    event_id = str(uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()
    serialized_properties = json.dumps(
        properties or {},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    initialize_event_store()

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO product_events (
                id,
                user_id,
                event_name,
                call_id,
                occurred_at,
                properties_json,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                user_id,
                clean_event_name,
                call_id,
                occurred_at,
                serialized_properties,
                source,
            ),
        )
        connection.commit()

    return event_id


def list_product_events(
    *,
    user_id: str | None = None,
    event_name: str | None = None,
    call_id: str | None = None,
) -> list[dict[str, Any]]:
    initialize_event_store()

    clauses: list[str] = []
    values: list[str] = []

    if user_id is not None:
        clauses.append("user_id = ?")
        values.append(user_id)

    if event_name is not None:
        clauses.append("event_name = ?")
        values.append(event_name)

    if call_id is not None:
        clauses.append("call_id = ?")
        values.append(call_id)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                user_id,
                event_name,
                call_id,
                occurred_at,
                properties_json,
                source
            FROM product_events
            {where}
            ORDER BY occurred_at ASC
            """,
            values,
        ).fetchall()

    result: list[dict[str, Any]] = []

    for row in rows:
        try:
            properties = json.loads(row["properties_json"])
        except (json.JSONDecodeError, TypeError):
            properties = {}

        result.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "event_name": row["event_name"],
                "call_id": row["call_id"],
                "occurred_at": row["occurred_at"],
                "properties": properties,
                "source": row["source"],
            }
        )

    return result
