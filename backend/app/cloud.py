from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
MIGRATIONS_DIRECTORY = PROJECT_ROOT / "backend" / "migrations"


@dataclass(frozen=True)
class CloudConfig:
    enabled: bool
    required: bool
    database_url: str | None
    s3_endpoint_url: str | None
    s3_bucket: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    s3_region: str
    s3_prefix: str

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def object_storage_configured(self) -> bool:
        return bool(
            self.s3_bucket
            and self.s3_access_key_id
            and self.s3_secret_access_key
        )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def load_cloud_config() -> CloudConfig:
    return CloudConfig(
        enabled=_env_bool("TCA_CLOUD_ENABLED"),
        required=_env_bool("TCA_CLOUD_REQUIRED"),
        database_url=os.getenv("DATABASE_URL") or None,
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        s3_bucket=os.getenv("S3_BUCKET") or None,
        s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID") or None,
        s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY") or None,
        s3_region=os.getenv("S3_REGION", "auto").strip() or "auto",
        s3_prefix=os.getenv("S3_OBJECT_PREFIX", "tca/").strip("/"),
    )


def _require_psycopg():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "Cloud PostgreSQL support requires psycopg. "
            "Install the backend requirements before enabling TCA_CLOUD_ENABLED."
        ) from error

    return psycopg


def _require_boto3():
    try:
        import boto3
    except ImportError as error:
        raise RuntimeError(
            "Cloud object storage support requires boto3. "
            "Install the backend requirements before enabling TCA_CLOUD_ENABLED."
        ) from error

    return boto3


def _database_connection():
    config = load_cloud_config()

    if not config.database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    psycopg = _require_psycopg()
    return psycopg.connect(
        config.database_url,
        connect_timeout=8,
    )


def cloud_database_connection():
    """Return a configured cloud PostgreSQL connection for feature services."""
    return _database_connection()


def _object_storage_client():
    config = load_cloud_config()

    if not config.object_storage_configured:
        raise RuntimeError(
            "S3 object storage is not fully configured."
        )

    boto3 = _require_boto3()

    kwargs: dict[str, Any] = {
        "service_name": "s3",
        "region_name": config.s3_region,
        "aws_access_key_id": config.s3_access_key_id,
        "aws_secret_access_key": config.s3_secret_access_key,
    }

    if config.s3_endpoint_url:
        kwargs["endpoint_url"] = config.s3_endpoint_url

    return boto3.client(**kwargs)


def _migration_statements() -> list[str]:
    migration_files = sorted(
        MIGRATIONS_DIRECTORY.glob("*.sql")
    )

    if not migration_files:
        raise RuntimeError(
            f"No cloud migration files found in {MIGRATIONS_DIRECTORY}"
        )

    statements: list[str] = []

    for migration_file in migration_files:
        sql = migration_file.read_text(
            encoding="utf-8"
        )
        statements.extend(
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        )

    return statements


def initialize_cloud_foundation() -> dict[str, Any]:
    config = load_cloud_config()

    if not config.enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "database": "disabled",
            "object_storage": "disabled",
        }

    result: dict[str, Any] = {
        "enabled": True,
        "status": "ok",
        "database": "not_configured",
        "object_storage": "not_configured",
    }

    if config.database_configured:
        try:
            with _database_connection() as connection:
                with connection.cursor() as cursor:
                    for statement in _migration_statements():
                        cursor.execute(statement)

                connection.commit()

            result["database"] = "ok"
        except Exception as error:
            result["database"] = f"error: {error}"
            result["status"] = "degraded"

            if config.required:
                raise RuntimeError(
                    "Required cloud PostgreSQL initialization failed: "
                    f"{error}"
                ) from error
    else:
        result["status"] = "degraded"

        if config.required:
            raise RuntimeError(
                "TCA_CLOUD_REQUIRED is enabled but DATABASE_URL is missing."
            )

    if config.object_storage_configured:
        try:
            client = _object_storage_client()
            client.head_bucket(Bucket=config.s3_bucket)
            result["object_storage"] = "ok"
        except Exception as error:
            result["object_storage"] = f"error: {error}"
            result["status"] = "degraded"

            if config.required:
                raise RuntimeError(
                    "Required cloud object storage check failed: "
                    f"{error}"
                ) from error
    else:
        if config.required:
            result["status"] = "degraded"

    return result


def cloud_health() -> dict[str, Any]:
    config = load_cloud_config()

    if not config.enabled:
        return {
            "status": "disabled",
            "enabled": False,
            "required": config.required,
            "database": {
                "configured": config.database_configured,
                "status": "disabled",
            },
            "object_storage": {
                "configured": config.object_storage_configured,
                "status": "disabled",
            },
        }

    database_status = "not_configured"
    database_error = None

    if config.database_configured:
        try:
            with _database_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()

            database_status = "ok"
        except Exception as error:
            database_status = "error"
            database_error = str(error)

    object_storage_status = "not_configured"
    object_storage_error = None

    if config.object_storage_configured:
        try:
            client = _object_storage_client()
            client.head_bucket(Bucket=config.s3_bucket)
            object_storage_status = "ok"
        except Exception as error:
            object_storage_status = "error"
            object_storage_error = str(error)

    configured_statuses = [
        database_status
        for _ in [0]
        if config.database_configured
    ]

    if config.object_storage_configured:
        configured_statuses.append(
            object_storage_status
        )

    if not configured_statuses:
        overall_status = "degraded"
    elif all(status == "ok" for status in configured_statuses):
        overall_status = "ok"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "enabled": True,
        "required": config.required,
        "database": {
            "configured": config.database_configured,
            "status": database_status,
            "error": database_error,
        },
        "object_storage": {
            "configured": config.object_storage_configured,
            "status": object_storage_status,
            "bucket": config.s3_bucket,
            "error": object_storage_error,
        },
    }


def sync_cloud_user(user) -> bool:
    """
    Mirror the authenticated user into cloud PostgreSQL when cloud mode is
    enabled. This is foundation plumbing only; the local auth database remains
    authoritative until the Cloud Memory/Auth migration features are enabled.
    """
    config = load_cloud_config()

    if not config.enabled or not config.database_configured:
        return False

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tca_users (
                    id,
                    email,
                    name,
                    onboarding_completed,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    onboarding_completed = EXCLUDED.onboarding_completed,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    user.id,
                    user.email,
                    user.name,
                    user.onboarding_completed,
                    user.created_at,
                    datetime.now(timezone.utc),
                ),
            )

        connection.commit()

    return True


def object_key(user_id: str, relative_path: str) -> str:
    config = load_cloud_config()

    clean_path = relative_path.strip("/")

    if not config.s3_prefix:
        return f"users/{user_id}/{clean_path}"

    return (
        f"{config.s3_prefix}/"
        f"users/{user_id}/"
        f"{clean_path}"
    )


def upload_file(
    *,
    user_id: str,
    relative_path: str,
    file_path: Path,
    content_type: str | None = None,
) -> str:
    config = load_cloud_config()

    if not config.enabled:
        raise RuntimeError(
            "Cloud mode is disabled."
        )

    if not config.object_storage_configured:
        raise RuntimeError(
            "Cloud object storage is not configured."
        )

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    key = object_key(
        user_id,
        relative_path,
    )

    extra_args: dict[str, Any] = {}

    if content_type:
        extra_args["ContentType"] = content_type

    client = _object_storage_client()

    if extra_args:
        client.upload_file(
            str(file_path),
            config.s3_bucket,
            key,
            ExtraArgs=extra_args,
        )
    else:
        client.upload_file(
            str(file_path),
            config.s3_bucket,
            key,
        )

    return key
