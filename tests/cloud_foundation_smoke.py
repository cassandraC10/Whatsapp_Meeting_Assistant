from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    # The smoke test must not require cloud credentials or network access.
    os.environ["TCA_CLOUD_ENABLED"] = "false"
    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from backend.app.cloud import (MIGRATIONS_DIRECTORY, cloud_health,
                                   load_cloud_config, object_key)

    config = load_cloud_config()

    assert config.enabled is False
    assert config.database_configured is False
    assert config.object_storage_configured is False

    health = cloud_health()

    assert health["status"] == "disabled"
    assert health["enabled"] is False

    migration = (
        MIGRATIONS_DIRECTORY
        / "001_cloud_foundation.sql"
    )

    assert migration.exists()
    sql = migration.read_text(encoding="utf-8")

    assert "tca_cloud_schema_migrations" in sql
    assert "tca_users" in sql
    assert "tca_objects" in sql

    os.environ["TCA_CLOUD_ENABLED"] = "true"
    os.environ["S3_OBJECT_PREFIX"] = "tca"

    from backend.app.cloud import load_cloud_config as reload_config

    enabled_config = reload_config()
    assert enabled_config.enabled is True
    assert object_key(
        "user-123",
        "calls/call-123/notes.json",
    ) == "tca/users/user-123/calls/call-123/notes.json"

    print("Cloud Foundation smoke test passed.")


if __name__ == "__main__":
    main()
