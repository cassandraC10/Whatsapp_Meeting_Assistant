"""Feature 3 identity smoke tests that do not require Gemini."""

import tempfile
from pathlib import Path

from backend.app import auth as auth_module
from backend.app import repository as repository_module


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_module.AUTH_DATABASE_PATH = root / "auth.db"
        auth_module.initialize_auth_database()

        user = auth_module.create_user(
            "Cassie Oliver",
            "CASSIE@example.com",
            "password123",
        )
        assert user.onboarding_completed is False

        updated = auth_module.update_user_profile(
            user.id,
            "Cassie O",
            True,
        )
        assert updated.name == "Cassie O"
        assert updated.onboarding_completed is True

        repository_module.CALLS_DIRECTORY = root / "calls"
        repository_module.CALLS_DIRECTORY.mkdir(parents=True, exist_ok=True)
        repository = repository_module.CallRepository()
        call = repository.create("Call with Jane", user_id=user.id)
        assert repository.get(call.id, user_id=user.id) is not None

    print("Feature 3 identity smoke test: PASS")


if __name__ == "__main__":
    main()
