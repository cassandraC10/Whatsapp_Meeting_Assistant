"""Standalone Feature 2 ownership smoke test.

Run from the project root with the backend environment available:
    python tests/feature2_ownership_smoke.py
"""

import tempfile
from pathlib import Path

from backend.app import auth as auth_module
from backend.app import repository as repository_module
from backend.app.models import CallStatus


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repository_module.CALLS_DIRECTORY = root / "calls"
        repository_module.CALLS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        auth_module.AUTH_DATABASE_PATH = root / "auth.db"
        auth_module.initialize_auth_database()

        repository = repository_module.CallRepository()
        user_a = auth_module.create_user("User A", "a@example.com", "password123")
        user_b = auth_module.create_user("User B", "b@example.com", "password123")

        call_a = repository.create("A private call", user_id=user_a.id)
        call_b = repository.create("B private call", user_id=user_b.id)

        call_a.status = CallStatus.COMPLETED
        call_b.status = CallStatus.COMPLETED
        repository.save(call_a)
        repository.save(call_b)

        assert [call.id for call in repository.list_all(user_id=user_a.id)] == [call_a.id]
        assert [call.id for call in repository.list_all(user_id=user_b.id)] == [call_b.id]
        assert repository.get(call_a.id, user_id=user_b.id) is None
        assert repository.get(call_b.id, user_id=user_a.id) is None

        legacy = repository.create("Legacy V0.4 call")
        assert repository.claim_legacy_calls(user_a.id) == 1
        assert repository.get(legacy.id, user_id=user_a.id) is not None
        assert repository.claim_legacy_calls(user_b.id) == 0
        assert repository.get(legacy.id, user_id=user_b.id) is None

    print("Feature 2 ownership smoke test: PASS")


if __name__ == "__main__":
    main()
