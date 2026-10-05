"""Smoke test for browser -> Windows Capture authentication handoff."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.auth import (  # noqa: E402
    create_capture_handoff,
    create_user,
    exchange_capture_handoff,
    initialize_auth_database,
)


def main() -> None:
    initialize_auth_database()

    suffix = uuid4().hex[:10]
    email = f"capture-smoke-{suffix}@example.com"
    user = create_user(
        name="Capture Smoke",
        email=email,
        password="capture-smoke-password",
    )

    code, expires_at = create_capture_handoff(user)
    assert code
    assert expires_at > 0

    exchanged = exchange_capture_handoff(code)
    assert exchanged is not None
    assert exchanged.id == user.id
    assert exchanged.email == user.email

    second_exchange = exchange_capture_handoff(code)
    assert second_exchange is None

    print("Capture auth smoke test passed.")


if __name__ == "__main__":
    main()
