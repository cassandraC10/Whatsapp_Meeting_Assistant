"""Feature 9 analytics + AI usage smoke test."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.analytics import (
    build_analytics_snapshot,
    initialize_analytics_store,
    record_ai_usage,
)
from backend.app.auth import create_user, initialize_auth_database
from backend.app.event_store import initialize_event_store, record_product_event


def main() -> None:
    initialize_auth_database()
    initialize_event_store()
    initialize_analytics_store()

    suffix = uuid4().hex[:10]
    user = create_user(
        name="Analytics Smoke",
        email=f"analytics-smoke-{suffix}@example.com",
        password="analytics-smoke-password",
    )

    record_product_event(
        user_id=user.id,
        event_name="recording_finished",
        call_id="analytics-call",
        properties={"duration_seconds": 125},
    )
    record_product_event(
        user_id=user.id,
        event_name="processing_started",
        call_id="analytics-call",
    )
    record_product_event(
        user_id=user.id,
        event_name="processing_completed",
        call_id="analytics-call",
    )
    record_product_event(
        user_id=user.id,
        event_name="feedback_submitted",
        call_id="analytics-call",
        properties={"rating": "helpful"},
    )
    record_product_event(
        user_id=user.id,
        event_name="search_used",
        properties={"query_length": 5, "result_count": 1},
    )

    os.environ["TCA_GEMINI_INPUT_COST_USD_PER_1M"] = "1.50"
    os.environ["TCA_GEMINI_OUTPUT_COST_USD_PER_1M"] = "9.00"
    record_ai_usage(
        user_id=user.id,
        call_id="analytics-call",
        operation="transcription",
        model="gemini-3.5-flash",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        estimated_cost_usd=0.006,
        latency_ms=1250,
    )

    snapshot = build_analytics_snapshot(user_id=user.id, days=30)

    assert snapshot["scope"] == "user"
    assert snapshot["overview"]["recording_seconds"] == 125.0
    assert snapshot["processing"]["completed"] >= 1
    assert snapshot["processing"]["success_rate"] == 100.0
    assert snapshot["overview"]["feedback_helpful"] >= 1
    assert snapshot["overview"]["searches"] >= 1
    assert snapshot["ai_usage"]["total_tokens"] >= 1500
    assert snapshot["ai_usage"]["estimated_cost_usd"] is not None
    assert any(
        item["operation"] == "transcription"
        for item in snapshot["ai_usage"]["by_operation"]
    )

    print("Analytics smoke test passed.")


if __name__ == "__main__":
    main()
