from __future__ import annotations

import json
import os
import sqlite3
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.cloud import cloud_database_connection, load_cloud_config
from backend.app.event_store import list_product_events

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ANALYTICS_DATABASE_PATH = BACKEND_ROOT / "data" / "tca_auth.db"
ANALYTICS_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

_ai_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "tca_ai_context",
    default=None,
)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(ANALYTICS_DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_analytics_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_usage (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                call_id TEXT,
                operation TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'gemini',
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                cached_tokens INTEGER NOT NULL DEFAULT 0,
                thoughts_tokens INTEGER NOT NULL DEFAULT 0,
                estimated_cost_usd REAL,
                status TEXT NOT NULL DEFAULT 'success',
                latency_ms INTEGER,
                occurred_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_usage_user_time
            ON ai_usage(user_id, occurred_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_usage_operation_time
            ON ai_usage(operation, occurred_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_usage_call
            ON ai_usage(call_id)
            """
        )
        connection.commit()


def set_ai_context(
    *,
    user_id: str,
    call_id: str | None,
    operation: str,
) -> Any:
    return _ai_context.set(
        {
            "user_id": user_id,
            "call_id": call_id,
            "operation": operation,
            "started_at": time.perf_counter(),
        }
    )


def reset_ai_context(token: Any) -> None:
    _ai_context.reset(token)


def _configured_pricing() -> tuple[float | None, float | None]:
    def read(name: str) -> float | None:
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

    return (
        read("TCA_GEMINI_INPUT_COST_USD_PER_1M"),
        read("TCA_GEMINI_OUTPUT_COST_USD_PER_1M"),
    )


def _usage_value(metadata: Any, *names: str) -> int:
    for name in names:
        value = getattr(metadata, name, None)
        if value is None and isinstance(metadata, dict):
            value = metadata.get(name)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                continue
    return 0


def record_gemini_response(
    response: Any,
    *,
    operation: str | None = None,
) -> None:
    context = _ai_context.get()
    if not context:
        return

    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return

    input_tokens = _usage_value(
        metadata,
        "prompt_token_count",
        "input_token_count",
    )
    output_tokens = _usage_value(
        metadata,
        "candidates_token_count",
        "response_token_count",
        "output_token_count",
    )
    total_tokens = _usage_value(metadata, "total_token_count")
    cached_tokens = _usage_value(
        metadata,
        "cached_content_token_count",
        "cache_read_input_tokens",
    )
    thoughts_tokens = _usage_value(
        metadata,
        "thoughts_token_count",
        "thinking_token_count",
    )

    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    input_price, output_price = _configured_pricing()
    estimated_cost: float | None = None
    if input_price is not None and output_price is not None:
        estimated_cost = (
            input_tokens / 1_000_000 * input_price
            + output_tokens / 1_000_000 * output_price
        )

    latency_ms = max(
        0,
        int((time.perf_counter() - float(context["started_at"])) * 1000),
    )

    record_ai_usage(
        user_id=str(context["user_id"]),
        call_id=context.get("call_id"),
        operation=operation or str(context["operation"]),
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        thoughts_tokens=thoughts_tokens,
        estimated_cost_usd=estimated_cost,
        latency_ms=latency_ms,
    )


def record_ai_usage(
    *,
    user_id: str,
    call_id: str | None,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    cached_tokens: int = 0,
    thoughts_tokens: int = 0,
    estimated_cost_usd: float | None = None,
    status: str = "success",
    latency_ms: int | None = None,
) -> str:
    initialize_analytics_store()

    usage_id = str(uuid4())
    occurred_at = datetime.now(timezone.utc).isoformat()

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO ai_usage (
                id, user_id, call_id, operation, provider, model,
                input_tokens, output_tokens, total_tokens,
                cached_tokens, thoughts_tokens, estimated_cost_usd,
                status, latency_ms, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usage_id,
                user_id,
                call_id,
                operation,
                "gemini",
                model,
                max(0, int(input_tokens)),
                max(0, int(output_tokens)),
                max(0, int(total_tokens)),
                max(0, int(cached_tokens)),
                max(0, int(thoughts_tokens)),
                estimated_cost_usd,
                status,
                latency_ms,
                occurred_at,
            ),
        )
        connection.commit()

    _sync_ai_usage_to_cloud(
        usage_id=usage_id,
        user_id=user_id,
        call_id=call_id,
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        thoughts_tokens=thoughts_tokens,
        estimated_cost_usd=estimated_cost_usd,
        status=status,
        latency_ms=latency_ms,
        occurred_at=occurred_at,
    )

    return usage_id


def _cloud_database_ready() -> bool:
    config = load_cloud_config()
    return config.enabled and config.database_configured


def _sync_ai_usage_to_cloud(**payload: Any) -> None:
    if not _cloud_database_ready():
        return

    try:
        with cloud_database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO tca_ai_usage (
                        id, user_id, call_id, operation, provider, model,
                        input_tokens, output_tokens, total_tokens,
                        cached_tokens, thoughts_tokens, estimated_cost_usd,
                        status, latency_ms, occurred_at
                    ) VALUES (
                        %s, %s, %s, %s, 'gemini', %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        payload["usage_id"],
                        payload["user_id"],
                        payload["call_id"],
                        payload["operation"],
                        payload["model"],
                        payload["input_tokens"],
                        payload["output_tokens"],
                        payload["total_tokens"],
                        payload["cached_tokens"],
                        payload["thoughts_tokens"],
                        payload["estimated_cost_usd"],
                        payload["status"],
                        payload["latency_ms"],
                        payload["occurred_at"],
                    ),
                )
            connection.commit()
    except Exception:
        return


def _fetch_local_usage(user_id: str | None, since: datetime) -> list[dict[str, Any]]:
    initialize_analytics_store()
    clauses = ["occurred_at >= ?"]
    values: list[Any] = [since.isoformat()]
    if user_id is not None:
        clauses.append("user_id = ?")
        values.append(user_id)

    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT operation, model, input_tokens, output_tokens,
                   total_tokens, estimated_cost_usd, status, occurred_at
            FROM ai_usage
            WHERE {' AND '.join(clauses)}
            ORDER BY occurred_at ASC
            """,
            values,
        ).fetchall()

    return [dict(row) for row in rows]


def _fetch_cloud_usage(user_id: str | None, since: datetime) -> list[dict[str, Any]]:
    if not _cloud_database_ready():
        return []

    try:
        with cloud_database_connection() as connection:
            with connection.cursor() as cursor:
                if user_id is None:
                    cursor.execute(
                        """
                        SELECT operation, model, input_tokens, output_tokens,
                               total_tokens, estimated_cost_usd, status, occurred_at
                        FROM tca_ai_usage
                        WHERE occurred_at >= %s
                        ORDER BY occurred_at ASC
                        """,
                        (since,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT operation, model, input_tokens, output_tokens,
                               total_tokens, estimated_cost_usd, status, occurred_at
                        FROM tca_ai_usage
                        WHERE user_id = %s AND occurred_at >= %s
                        ORDER BY occurred_at ASC
                        """,
                        (user_id, since),
                    )
                columns = [description.name for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        return []


def _fetch_events(user_id: str | None, since: datetime) -> list[dict[str, Any]]:
    if _cloud_database_ready():
        try:
            with cloud_database_connection() as connection:
                with connection.cursor() as cursor:
                    if user_id is None:
                        cursor.execute(
                            """
                            SELECT id, user_id, event_name, call_id, occurred_at,
                                   properties_json, source
                            FROM tca_product_events
                            WHERE occurred_at >= %s
                            ORDER BY occurred_at ASC
                            """,
                            (since,),
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT id, user_id, event_name, call_id, occurred_at,
                                   properties_json, source
                            FROM tca_product_events
                            WHERE user_id = %s AND occurred_at >= %s
                            ORDER BY occurred_at ASC
                            """,
                            (user_id, since),
                        )
                    columns = [description.name for description in cursor.description]
                    result = []
                    for row in cursor.fetchall():
                        item = dict(zip(columns, row))
                        raw = item.get("properties_json")
                        if isinstance(raw, str):
                            try:
                                item["properties"] = json.loads(raw)
                            except json.JSONDecodeError:
                                item["properties"] = {}
                        else:
                            item["properties"] = raw or {}
                        result.append(item)
                    return result
        except Exception:
            pass

    return [
        event
        for event in list_product_events(user_id=user_id)
        if datetime.fromisoformat(event["occurred_at"]) >= since
    ]


def _event_count(events: list[dict[str, Any]], name: str) -> int:
    return sum(1 for event in events if event.get("event_name") == name)


def _sum_event_duration(events: list[dict[str, Any]]) -> float:
    total = 0.0
    for event in events:
        properties = event.get("properties") or {}
        try:
            total += float(properties.get("duration_seconds", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def build_analytics_snapshot(
    *,
    user_id: str | None,
    days: int = 30,
) -> dict[str, Any]:
    days = min(365, max(1, int(days)))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    events = _fetch_events(user_id, since)
    usage = _fetch_cloud_usage(user_id, since) if _cloud_database_ready() else _fetch_local_usage(user_id, since)

    event_counts = Counter(str(event.get("event_name")) for event in events)
    recording_durations = _sum_event_duration(
        [event for event in events if event.get("event_name") == "recording_finished"]
    )
    conversation_ids = {
        event.get("call_id")
        for event in events
        if event.get("call_id")
    }

    feedback_helpful = sum(
        1
        for event in events
        if event.get("event_name") in {"feedback_submitted", "feedback_updated"}
        and (event.get("properties") or {}).get("rating") == "helpful"
    )
    feedback_needs_work = sum(
        1
        for event in events
        if event.get("event_name") in {"feedback_submitted", "feedback_updated"}
        and (event.get("properties") or {}).get("rating") == "needs_work"
    )

    input_tokens = sum(int(row.get("input_tokens") or 0) for row in usage)
    output_tokens = sum(int(row.get("output_tokens") or 0) for row in usage)
    total_tokens = sum(int(row.get("total_tokens") or 0) for row in usage)
    known_costs = [row.get("estimated_cost_usd") for row in usage if row.get("estimated_cost_usd") is not None]
    estimated_cost = sum(float(value) for value in known_costs) if known_costs else None

    by_operation: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": None,
        }
    )
    for row in usage:
        bucket = by_operation[str(row.get("operation") or "unknown")]
        bucket["requests"] += 1
        bucket["input_tokens"] += int(row.get("input_tokens") or 0)
        bucket["output_tokens"] += int(row.get("output_tokens") or 0)
        bucket["total_tokens"] += int(row.get("total_tokens") or 0)
        if row.get("estimated_cost_usd") is not None:
            bucket["estimated_cost_usd"] = (
                float(bucket["estimated_cost_usd"] or 0)
                + float(row["estimated_cost_usd"])
            )

    active_days = len({str(event.get("occurred_at", ""))[:10] for event in events})
    completed = event_counts["processing_completed"]
    failed = event_counts["processing_failed"]
    processing_attempts = completed + failed
    success_rate = (
        round(completed / processing_attempts * 100, 1)
        if processing_attempts
        else None
    )
    feedback_total = feedback_helpful + feedback_needs_work

    return {
        "scope": "user" if user_id is not None else "all",
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "active_days": active_days,
            "conversation_events": len(conversation_ids),
            "capture_opens": event_counts["capture_opened"],
            "recordings_started": event_counts["recording_started"],
            "recordings_finished": event_counts["recording_finished"],
            "recording_seconds": round(recording_durations, 1),
            "searches": event_counts["search_used"],
            "ask_questions": event_counts["ask_tca_used"],
            "feedback_submitted": event_counts["feedback_submitted"],
            "feedback_updated": event_counts["feedback_updated"],
            "feedback_helpful": feedback_helpful,
            "feedback_needs_work": feedback_needs_work,
            "feedback_helpful_rate": (
                round(feedback_helpful / feedback_total * 100, 1)
                if feedback_total
                else None
            ),
        },
        "processing": {
            "started": event_counts["processing_started"],
            "completed": completed,
            "failed": failed,
            "success_rate": success_rate,
        },
        "ai_usage": {
            "requests": len(usage),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 8) if estimated_cost is not None else None,
            "pricing_configured": estimated_cost is not None,
            "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
            "by_operation": [
                {"operation": operation, **values}
                for operation, values in sorted(by_operation.items())
            ],
        },
        "events": [
            {"event_name": name, "count": count}
            for name, count in sorted(event_counts.items())
        ],
    }
