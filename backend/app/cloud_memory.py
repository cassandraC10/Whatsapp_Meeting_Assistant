from __future__ import annotations

import hashlib
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.cloud import (
    _database_connection,
    _object_storage_client,
    load_cloud_config,
    object_key,
)
from backend.app.models import Call, CallStatus


MEMORY_FILES = (
    "metadata.json",
    "notes.json",
    "tasks.json",
    "combined_transcript.txt",
    "transcript.json",
    "my_transcript.txt",
    "their_transcript.txt",
    "meeting.wav",
    "mic_raw.wav",
    "system_raw.wav",
    "mic_raw.webm",
    "system_raw.webm",
    "mic_raw.ogg",
    "system_raw.ogg",
    "mic_raw.mp4",
    "system_raw.mp4",
    "mic_raw.m4a",
    "system_raw.m4a",
    "mic_raw.mp3",
    "system_raw.mp3",
)

MEMORY_TEXT_FILES = {
    "notes.json",
    "tasks.json",
    "combined_transcript.txt",
    "transcript.json",
    "my_transcript.txt",
    "their_transcript.txt",
}


def cloud_memory_available() -> bool:
    config = load_cloud_config()
    return config.enabled and config.database_configured


def cloud_memory_object_storage_available() -> bool:
    config = load_cloud_config()
    return config.enabled and config.object_storage_configured


def _json_file(directory: Path, filename: str) -> Any:
    path = directory / filename
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _text_file(directory: Path, filename: str) -> str | None:
    path = directory / filename
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _call_row(call: Call, directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    notes = _json_file(directory, "notes.json")
    tasks = _json_file(directory, "tasks.json")
    transcript = _text_file(directory, "combined_transcript.txt")
    transcript_json = _json_file(directory, "transcript.json")

    payload = {
        "id": call.id,
        "user_id": call.user_id,
        "title": call.title,
        "created_at": call.created_at,
        "duration_seconds": call.duration_seconds,
        "status": call.status.value,
        "failure_reason": call.failure_reason,
        "notes_json": json.dumps(notes, ensure_ascii=False) if notes is not None else None,
        "tasks_json": json.dumps(tasks, ensure_ascii=False) if tasks is not None else None,
        "transcript_text": transcript,
        "transcript_json": json.dumps(transcript_json, ensure_ascii=False)
        if transcript_json is not None
        else None,
        "updated_at": datetime.now(timezone.utc),
    }
    return payload, {
        "notes": notes,
        "tasks": tasks,
        "transcript": transcript,
        "transcript_json": transcript_json,
    }


def sync_call_to_cloud(
    *,
    call: Call,
    call_directory: Path,
) -> bool:
    """Persist a call's durable memory to PostgreSQL and its files to S3."""
    if not cloud_memory_available():
        return False

    if not call.user_id:
        raise RuntimeError("Cannot sync a call without an owner.")

    payload, _ = _call_row(call, call_directory)

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tca_calls (
                    id, user_id, title, created_at, duration_seconds,
                    status, failure_reason, notes_json, tasks_json,
                    transcript_text, transcript_json, updated_at
                )
                VALUES (
                    %(id)s, %(user_id)s, %(title)s, %(created_at)s,
                    %(duration_seconds)s, %(status)s, %(failure_reason)s,
                    %(notes_json)s::jsonb, %(tasks_json)s::jsonb,
                    %(transcript_text)s, %(transcript_json)s::jsonb,
                    %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    title = EXCLUDED.title,
                    created_at = EXCLUDED.created_at,
                    duration_seconds = EXCLUDED.duration_seconds,
                    status = EXCLUDED.status,
                    failure_reason = EXCLUDED.failure_reason,
                    notes_json = EXCLUDED.notes_json,
                    tasks_json = EXCLUDED.tasks_json,
                    transcript_text = EXCLUDED.transcript_text,
                    transcript_json = EXCLUDED.transcript_json,
                    updated_at = EXCLUDED.updated_at
                """,
                payload,
            )
        connection.commit()

    config = load_cloud_config()
    if not config.object_storage_configured:
        if config.required:
            raise RuntimeError(
                "Cloud Memory requires S3-compatible object storage when "
                "TCA_CLOUD_REQUIRED=true."
            )
        return True

    client = _object_storage_client()

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            for relative_name in MEMORY_FILES:
                file_path = call_directory / relative_name
                if not file_path.exists() or not file_path.is_file():
                    continue

                key = object_key(call.user_id, f"calls/{call.id}/{relative_name}")
                content_type = mimetypes.guess_type(relative_name)[0] or "application/octet-stream"

                # Avoid re-uploading unchanged objects on metadata/title/task updates.
                existing_sha = None
                cursor.execute(
                    "SELECT sha256 FROM tca_call_objects WHERE call_id = %s AND relative_path = %s",
                    (call.id, relative_name),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    existing_sha = existing_row["sha256"]

                current_sha = _sha256(file_path)
                if existing_sha != current_sha:
                    client.upload_file(
                        str(file_path),
                        config.s3_bucket,
                        key,
                        ExtraArgs={"ContentType": content_type},
                    )

                cursor.execute(
                    """
                    INSERT INTO tca_call_objects (
                        call_id, user_id, relative_path, object_key,
                        content_type, size_bytes, sha256, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (call_id, relative_path) DO UPDATE SET
                        object_key = EXCLUDED.object_key,
                        content_type = EXCLUDED.content_type,
                        size_bytes = EXCLUDED.size_bytes,
                        sha256 = EXCLUDED.sha256,
                        created_at = EXCLUDED.created_at
                    """,
                    (
                        call.id,
                        call.user_id,
                        relative_name,
                        key,
                        content_type,
                        file_path.stat().st_size,
                        current_sha,
                        datetime.now(timezone.utc),
                    ),
                )

        connection.commit()

    return True


def _row_to_call(row: Any) -> Call:
    return Call(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        created_at=row["created_at"],
        duration_seconds=float(row["duration_seconds"] or 0),
        status=CallStatus(row["status"]),
        failure_reason=row["failure_reason"],
    )


def get_cloud_call(call_id: str, user_id: str | None = None) -> Call | None:
    if not cloud_memory_available():
        return None

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            if user_id is None:
                cursor.execute(
                    "SELECT * FROM tca_calls WHERE id = %s",
                    (call_id,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM tca_calls WHERE id = %s AND user_id = %s",
                    (call_id, user_id),
                )
            row = cursor.fetchone()

    return _row_to_call(row) if row else None


def list_cloud_calls(user_id: str) -> list[Call]:
    if not cloud_memory_available():
        return []

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM tca_calls
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

    return [_row_to_call(row) for row in rows]


def get_cloud_memory(call_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    if not cloud_memory_available():
        return None

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            if user_id is None:
                cursor.execute(
                    "SELECT * FROM tca_calls WHERE id = %s",
                    (call_id,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM tca_calls WHERE id = %s AND user_id = %s",
                    (call_id, user_id),
                )
            row = cursor.fetchone()

    if not row:
        return None

    def parse_json(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    return {
        "call": _row_to_call(row),
        "notes": parse_json(row["notes_json"]) or {},
        "tasks": parse_json(row["tasks_json"]) or [],
        "transcript": row["transcript_text"] or "",
        "transcript_json": parse_json(row["transcript_json"]),
    }


def hydrate_call_from_cloud(
    *,
    call_id: str,
    user_id: str | None,
    directory: Path,
    include_audio: bool = False,
) -> bool:
    memory = get_cloud_memory(call_id, user_id=user_id)
    if memory is None:
        return False

    directory.mkdir(parents=True, exist_ok=True)
    call = memory["call"]

    (directory / "metadata.json").write_text(
        json.dumps(call.model_dump(mode="json"), indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    if memory["notes"]:
        (directory / "notes.json").write_text(
            json.dumps(memory["notes"], indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    if memory["tasks"]:
        (directory / "tasks.json").write_text(
            json.dumps(memory["tasks"], indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    if memory["transcript"]:
        (directory / "combined_transcript.txt").write_text(
            memory["transcript"],
            encoding="utf-8",
        )

    if memory["transcript_json"] is not None:
        (directory / "transcript.json").write_text(
            json.dumps(memory["transcript_json"], indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    if not cloud_memory_object_storage_available():
        return True

    config = load_cloud_config()
    client = _object_storage_client()

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relative_path, object_key
                FROM tca_call_objects
                WHERE call_id = %s AND user_id = %s
                """,
                (call_id, user_id),
            )
            objects = cursor.fetchall()

    for row in objects:
        relative_path = row["relative_path"]
        if not include_audio and relative_path.rsplit(".", 1)[-1].casefold() in {"wav", "webm", "ogg", "mp4", "m4a", "mp3"}:
            continue
        target = directory / relative_path
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(
            config.s3_bucket,
            row["object_key"],
            str(target),
        )

    return True


def delete_cloud_call(call_id: str, user_id: str) -> bool:
    if not cloud_memory_available():
        return False

    config = load_cloud_config()

    object_rows = []
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT object_key
                FROM tca_call_objects
                WHERE call_id = %s AND user_id = %s
                """,
                (call_id, user_id),
            )
            object_rows = cursor.fetchall()

    if object_rows and config.object_storage_configured:
        client = _object_storage_client()
        for row in object_rows:
            try:
                client.delete_object(
                    Bucket=config.s3_bucket,
                    Key=row["object_key"],
                )
            except Exception:
                if config.required:
                    raise

    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM tca_calls WHERE id = %s AND user_id = %s",
                (call_id, user_id),
            )
            deleted = cursor.rowcount > 0
        connection.commit()

    return deleted
