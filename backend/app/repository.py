import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.models import Call, CallStatus


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

CALLS_DIRECTORY = (
    BACKEND_ROOT
    / "data"
    / "calls"
)

CALLS_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


class CallRepository:
    def create(
        self,
        title: str | None = None,
    ) -> Call:
        call_id = str(
            uuid4()
        )

        clean_title = (
            title.strip()
            if title
            and title.strip()
            else "Untitled call"
        )

        call = Call(
            id=call_id,
            title=clean_title,
            created_at=datetime.now(
                timezone.utc
            ),
            duration_seconds=0,
            status=CallStatus.CREATED,
        )

        call_directory = (
            self._call_directory(
                call_id
            )
        )

        call_directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        self.save(
            call
        )

        return call

    def save(
        self,
        call: Call,
    ) -> None:
        call_directory = (
            self._call_directory(
                call.id
            )
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
            self._call_directory(
                call_id
            )
            / "metadata.json"
        )

        if (
            not metadata_file.exists()
        ):
            return None

        data = json.loads(
            metadata_file.read_text(
                encoding="utf-8"
            )
        )

        return (
            Call.model_validate(
                data
            )
        )

    def list_all(
        self,
    ) -> list[Call]:
        calls: list[Call] = []

        if (
            not CALLS_DIRECTORY.exists()
        ):
            return calls

        for directory in (
            CALLS_DIRECTORY.iterdir()
        ):
            if (
                not directory.is_dir()
            ):
                continue

            call = self.get(
                directory.name
            )

            if call:
                calls.append(
                    call
                )

        calls.sort(
            key=lambda item: (
                item.created_at
            ),
            reverse=True,
        )

        return calls

    def search(
        self,
        query: str,
    ) -> list[dict]:
        clean_query = (
            query.strip()
        )

        if not clean_query:
            return []

        query_folded = (
            clean_query.casefold()
        )

        results: list[dict] = []

        for call in self.list_all():
            searchable_sections = (
                self._searchable_sections(
                    call
                )
            )

            matched_sections: list[
                str
            ] = []

            best_snippet = ""
            best_score = 0

            for (
                section_name,
                section_text,
                section_weight,
            ) in searchable_sections:
                if not section_text:
                    continue

                folded_text = (
                    section_text
                    .casefold()
                )

                occurrence_count = (
                    folded_text.count(
                        query_folded
                    )
                )

                if occurrence_count == 0:
                    continue

                matched_sections.append(
                    section_name
                )

                score = (
                    section_weight
                    * occurrence_count
                )

                if score > best_score:
                    best_score = score

                    best_snippet = (
                        self._make_snippet(
                            text=section_text,
                            query=clean_query,
                        )
                    )

            if not matched_sections:
                continue

            results.append(
                {
                    "call": call,
                    "snippet": (
                        best_snippet
                    ),
                    "matched_in": (
                        list(
                            dict.fromkeys(
                                matched_sections
                            )
                        )
                    ),
                    "_score": (
                        best_score
                    ),
                }
            )

        results.sort(
            key=lambda item: (
                item["_score"],
                item[
                    "call"
                ].created_at,
            ),
            reverse=True,
        )

        for result in results:
            result.pop(
                "_score",
                None,
            )

        return results

    def delete(
        self,
        call_id: str,
    ) -> bool:
        call_directory = (
            self._call_directory(
                call_id
            )
        )

        if (
            not call_directory.exists()
        ):
            return False

        shutil.rmtree(
            call_directory
        )

        return True

    def get_directory(
        self,
        call_id: str,
    ) -> Path:
        return (
            self._call_directory(
                call_id
            )
        )

    def _call_directory(
        self,
        call_id: str,
    ) -> Path:
        return (
            CALLS_DIRECTORY
            / call_id
        )

    def _searchable_sections(
        self,
        call: Call,
    ) -> list[
        tuple[
            str,
            str,
            int,
        ]
    ]:
        sections: list[
            tuple[
                str,
                str,
                int,
            ]
        ] = [
            (
                "title",
                call.title,
                8,
            ),
        ]

        call_directory = (
            self._call_directory(
                call.id
            )
        )

        notes_file = (
            call_directory
            / "notes.json"
        )

        if notes_file.exists():
            try:
                notes = json.loads(
                    notes_file.read_text(
                        encoding="utf-8"
                    )
                )

            except (
                json.JSONDecodeError,
                OSError,
            ):
                notes = {}

            sections.extend(
                self._notes_sections(
                    notes
                )
            )

        transcript_file = (
            call_directory
            / "combined_transcript.txt"
        )

        if (
            transcript_file.exists()
        ):
            try:
                transcript = (
                    transcript_file
                    .read_text(
                        encoding="utf-8"
                    )
                )

            except OSError:
                transcript = ""

            if transcript:
                sections.append(
                    (
                        "transcript",
                        transcript,
                        1,
                    )
                )

        return sections

    def _notes_sections(
        self,
        notes: dict,
    ) -> list[
        tuple[
            str,
            str,
            int,
        ]
    ]:
        sections: list[
            tuple[
                str,
                str,
                int,
            ]
        ] = []

        field_weights = {
            "title": 8,
            "summary": 6,
            "key_points": 5,
            "decisions": 5,
            "my_action_items": 4,
            "their_action_items": 4,
            "important_dates": 4,
            "follow_up": 3,
        }

        for (
            field_name,
            weight,
        ) in field_weights.items():
            value = notes.get(
                field_name
            )

            text = (
                self._value_to_text(
                    value
                )
            )

            if text:
                sections.append(
                    (
                        field_name,
                        text,
                        weight,
                    )
                )

        return sections

    def _value_to_text(
        self,
        value,
    ) -> str:
        if value is None:
            return ""

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        if isinstance(
            value,
            (
                int,
                float,
                bool,
            ),
        ):
            return str(
                value
            )

        if isinstance(
            value,
            list,
        ):
            parts = [
                self._value_to_text(
                    item
                )
                for item in value
            ]

            return " ".join(
                part
                for part in parts
                if part
            )

        if isinstance(
            value,
            dict,
        ):
            parts = [
                self._value_to_text(
                    item
                )
                for item in (
                    value.values()
                )
            ]

            return " ".join(
                part
                for part in parts
                if part
            )

        return str(
            value
        )

    def _make_snippet(
        self,
        text: str,
        query: str,
        radius: int = 90,
    ) -> str:
        normalized_text = (
            re.sub(
                r"\s+",
                " ",
                text,
            )
            .strip()
        )

        if not normalized_text:
            return ""

        folded_text = (
            normalized_text.casefold()
        )

        folded_query = (
            query.casefold()
        )

        match_index = (
            folded_text.find(
                folded_query
            )
        )

        if match_index == -1:
            return (
                normalized_text[
                    : radius * 2
                ]
            )

        start = max(
            0,
            match_index
            - radius,
        )

        end = min(
            len(
                normalized_text
            ),
            match_index
            + len(query)
            + radius,
        )

        snippet = (
            normalized_text[
                start:end
            ]
        )

        if start > 0:
            snippet = (
                "…"
                + snippet
            )

        if (
            end
            < len(
                normalized_text
            )
        ):
            snippet = (
                snippet
                + "…"
            )

        return snippet