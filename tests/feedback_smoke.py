"""Feature 8 feedback + analytics event smoke test."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.auth import create_user, initialize_auth_database
from backend.app.event_store import (
    initialize_event_store,
    list_product_events,
)
from backend.app.feedback import (
    get_feedback,
    initialize_feedback_store,
    submit_feedback,
)
from backend.app.models import FeedbackRating
from backend.app.repository import CallRepository


def main() -> None:
    initialize_auth_database()
    initialize_event_store()
    initialize_feedback_store()

    suffix = uuid4().hex[:10]

    user = create_user(
        name="Feedback Smoke",
        email=f"feedback-smoke-{suffix}@example.com",
        password="feedback-smoke-password",
    )

    repository = CallRepository()

    call = repository.create(
        title="Feedback smoke conversation",
        user_id=user.id,
    )

    first = submit_feedback(
        user_id=user.id,
        call_id=call.id,
        rating=FeedbackRating.HELPFUL,
        comment="The memory was clear.",
    )

    assert first.rating == FeedbackRating.HELPFUL
    assert first.comment == "The memory was clear."

    saved = get_feedback(
        user_id=user.id,
        call_id=call.id,
    )

    assert saved is not None
    assert saved.rating == FeedbackRating.HELPFUL

    events = list_product_events(
        user_id=user.id,
        call_id=call.id,
    )

    assert len(events) == 1
    assert events[0]["event_name"] == "feedback_submitted"
    assert events[0]["properties"]["rating"] == "helpful"
    assert events[0]["properties"]["has_comment"] is True

    unchanged = submit_feedback(
        user_id=user.id,
        call_id=call.id,
        rating=FeedbackRating.HELPFUL,
        comment="The memory was clear.",
    )

    assert unchanged.id == first.id

    events_after_repeat = list_product_events(
        user_id=user.id,
        call_id=call.id,
    )

    assert len(events_after_repeat) == 1

    updated = submit_feedback(
        user_id=user.id,
        call_id=call.id,
        rating=FeedbackRating.NEEDS_WORK,
        comment="The next steps were too vague.",
    )

    assert updated.id == first.id
    assert updated.rating == FeedbackRating.NEEDS_WORK

    final_events = list_product_events(
        user_id=user.id,
        call_id=call.id,
    )

    assert len(final_events) == 2
    assert [event["event_name"] for event in final_events] == [
        "feedback_submitted",
        "feedback_updated",
    ]
    assert final_events[-1]["properties"]["rating"] == "needs_work"

    try:
        submit_feedback(
            user_id=user.id,
            call_id=call.id,
            rating=FeedbackRating.NEEDS_WORK,
            comment="x" * 2001,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Oversized feedback comment was accepted.")

    # Keep the smoke test from accumulating its temporary call payload.
    repository.delete(
        call.id,
        user_id=user.id,
    )

    print("Feedback smoke test passed.")


if __name__ == "__main__":
    main()
