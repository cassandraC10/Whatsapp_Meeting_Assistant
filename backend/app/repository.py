import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.models import Call, CallStatus


BACKEND_ROOT = Path(__file__).resolve().parent.parent

CALLS_DIRECTORY = BACKEND_ROOT / "data" / "calls"

CALLS_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


class CallRepository:
    def create(
        self,
        title: str | None = None,
    ) -> Call:
        call_id = str(uuid4())

        clean_title = (
            title.strip()
            if title and title.strip()
            else "Untitled call"
        )

        call = Call(
            id=call_id,
            title=clean_title,
            created_at=datetime.now(timezone.utc),
            duration_seconds=0,
            status=CallStatus.CREATED,
        )

        call_directory = self._call_directory(
            call_id
        )

        call_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        self.save(call)

        return call

    def save(
        self,
        call: Call,
    ) -> None:
        call_directory = self._call_directory(
            call.id
        )

        call_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        metadata_file = (
            call_directory
            / "metadata.json"
        )

        metadata_file.write_text(
            json.dumps(
                call.model_dump(
                    mode="json"
                ),
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def get(
        self,
        call_id: str,
    ) -> Call | None:
        metadata_file = (
            self._call_directory(call_id)
            / "metadata.json"
        )

        if not metadata_file.exists():
            return None

        data = json.loads(
            metadata_file.read_text(
                encoding="utf-8"
            )
        )

        return Call.model_validate(data)

    def list_all(self) -> list[Call]:
        calls = []

        if not CALLS_DIRECTORY.exists():
            return calls

        for directory in CALLS_DIRECTORY.iterdir():
            if not directory.is_dir():
                continue

            call = self.get(
                directory.name
            )

            if call:
                calls.append(call)

        calls.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return calls

    def get_directory(
        self,
        call_id: str,
    ) -> Path:
        return self._call_directory(
            call_id
        )

    def _call_directory(
        self,
        call_id: str,
    ) -> Path:
        return CALLS_DIRECTORY / call_id