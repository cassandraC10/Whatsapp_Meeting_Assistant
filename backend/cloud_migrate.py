from __future__ import annotations

import sys

from backend.app.auth import get_user, migrate_local_auth_users_to_cloud
from backend.app.cloud import (
    initialize_cloud_foundation,
    load_cloud_config,
    sync_cloud_user,
)


def main() -> int:
    config = load_cloud_config()

    if not config.enabled:
        print(
            "TCA_CLOUD_ENABLED is false. "
            "Set it to true before running cloud migrations."
        )
        return 1

    status = initialize_cloud_foundation()
    print(f"Cloud foundation: {status}")

    if status.get("database") != "ok":
        print("Cloud PostgreSQL is not ready.")
        return 1

    migrated_auth = migrate_local_auth_users_to_cloud()
    print(f"Migrated {migrated_auth} local auth accounts into cloud auth.")

    # Mirror all existing local-auth users into the foundation table.
    # Importing sqlite here keeps the cloud module provider-neutral.
    from backend.app.auth import AUTH_DATABASE_PATH, _connect

    synced = 0

    with _connect() as connection:
        rows = connection.execute(
            "SELECT id FROM users ORDER BY created_at"
        ).fetchall()

    for row in rows:
        user = get_user(str(row["id"]))
        if user is None:
            continue

        sync_cloud_user(user)
        synced += 1

    print(f"Synced {synced} local users into cloud PostgreSQL.")
    print("Cloud foundation migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
