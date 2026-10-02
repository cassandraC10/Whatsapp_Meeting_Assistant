from __future__ import annotations

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))


def main() -> None:
    os.environ["TCA_CLOUD_ENABLED"] = "false"
    os.environ["TCA_CLOUD_REQUIRED"] = "false"

    from backend.app.cloud_memory import cloud_memory_available
    from backend.app.cloud import load_cloud_config

    config = load_cloud_config()
    assert config.enabled is False
    assert cloud_memory_available() is False

    migration = Path(__file__).resolve().parents[1] / "backend" / "migrations" / "002_cloud_memory.sql"
    sql = migration.read_text(encoding="utf-8")

    required_markers = [
        "CREATE TABLE IF NOT EXISTS tca_calls",
        "CREATE TABLE IF NOT EXISTS tca_call_objects",
        "002_cloud_memory",
    ]

    for marker in required_markers:
        assert marker in sql, f"Missing cloud memory migration marker: {marker}"

    print("Cloud Memory smoke test passed.")


if __name__ == "__main__":
    main()
