import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from backend.app.models import (Call, CallStatus, Person, PersonDetail,
                                PersonTask, Task, TaskOwner)

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

    def update_title(
        self,
        call_id: str,
        title: str,
    ) -> Call | None:
        call = self.get(
            call_id
        )

        if call is None:
            return None

        cleaned_title = title.strip()

        if not cleaned_title:
            raise ValueError(
                "Call title cannot be empty."
            )

        call.title = cleaned_title
        self.save(call)

        notes_file = (
            self._call_directory(call_id)
            / "notes.json"
        )

        if notes_file.exists():
            try:
                notes = json.loads(
                    notes_file.read_text(
                        encoding="utf-8"
                    )
                )

                if isinstance(notes, dict):
                    notes["title"] = cleaned_title
                    notes_file.write_text(
                        json.dumps(
                            notes,
                            indent=4,
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
            except (
                json.JSONDecodeError,
                OSError,
            ):
                pass

        return call


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

    def get_tasks(
        self,
        call_id: str,
    ) -> list[Task]:
        call_directory = (
            self._call_directory(
                call_id
            )
        )

        if not call_directory.exists():
            return []

        tasks_file = (
            call_directory
            / "tasks.json"
        )

        if tasks_file.exists():
            try:
                raw_tasks = json.loads(
                    tasks_file.read_text(
                        encoding="utf-8"
                    )
                )
            except (
                json.JSONDecodeError,
                OSError,
            ):
                raw_tasks = []

            if not isinstance(
                raw_tasks,
                list,
            ):
                raw_tasks = []

            tasks: list[Task] = []

            for item in raw_tasks:
                try:
                    tasks.append(
                        Task.model_validate(
                            item
                        )
                    )
                except Exception:
                    continue

            return tasks

        tasks = self._build_tasks_from_notes(
            call_id
        )

        self.save_tasks(
            call_id,
            tasks,
        )

        return tasks

    def save_tasks(
        self,
        call_id: str,
        tasks: list[Task],
    ) -> None:
        call_directory = (
            self._call_directory(
                call_id
            )
        )

        call_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        tasks_file = (
            call_directory
            / "tasks.json"
        )

        tasks_file.write_text(
            json.dumps(
                [
                    task.model_dump(
                        mode="json"
                    )
                    for task in tasks
                ],
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def update_task(
        self,
        call_id: str,
        task_id: str,
        *,
        task_text: str | None = None,
        deadline: str | None = None,
        deadline_provided: bool = False,
        completed: bool | None = None,
    ) -> Task | None:
        tasks = self.get_tasks(
            call_id
        )

        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue

            if task_text is not None:
                task.task = task_text.strip()

            if deadline_provided:
                cleaned_deadline = (
                    deadline.strip()
                    if deadline is not None
                    else ""
                )
                task.deadline = (
                    cleaned_deadline
                    or None
                )

            if completed is not None:
                task.completed = completed

            tasks[index] = task

            self.save_tasks(
                call_id,
                tasks,
            )

            return task

        return None

    def delete_task(
        self,
        call_id: str,
        task_id: str,
    ) -> bool:
        tasks = self.get_tasks(
            call_id
        )

        remaining = [
            task
            for task in tasks
            if task.id != task_id
        ]

        if len(remaining) == len(tasks):
            return False

        self.save_tasks(
            call_id,
            remaining,
        )

        return True

    def _build_tasks_from_notes(
        self,
        call_id: str,
    ) -> list[Task]:
        call_directory = (
            self._call_directory(
                call_id
            )
        )

        notes_file = (
            call_directory
            / "notes.json"
        )

        if not notes_file.exists():
            return []

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
            return []

        tasks: list[Task] = []

        owner_fields = (
            (
                TaskOwner.ME,
                "my_action_items",
            ),
            (
                TaskOwner.THEM,
                "their_action_items",
            ),
        )

        for owner, field_name in owner_fields:
            items = notes.get(
                field_name,
                [],
            )

            if not isinstance(
                items,
                list,
            ):
                continue

            for item in items:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                task_text = str(
                    item.get(
                        "task",
                        "",
                    )
                    or ""
                ).strip()

                if not task_text:
                    continue

                deadline_value = item.get(
                    "deadline"
                )
                deadline = (
                    str(deadline_value).strip()
                    if deadline_value is not None
                    else None
                )

                if not deadline:
                    continue

                stable_key = (
                    f"tca-task:{call_id}:"
                    f"{owner.value}:"
                    f"{task_text.casefold()}:"
                    f"{deadline or ''}"
                )

                tasks.append(
                    Task(
                        id=str(
                            uuid5(
                                NAMESPACE_URL,
                                stable_key,
                            )
                        ),
                        call_id=call_id,
                        owner=owner,
                        task=task_text,
                        deadline=deadline,
                        owner_name=(
                            str(
                                item.get(
                                    "owner_name"
                                )
                                or ""
                            ).strip()
                            or None
                        ),
                        completed=False,
                    )
                )

        return tasks

    def list_people(self) -> list[Person]:
        people: dict[str, dict] = {}

        for call in self.list_all():
            for name in self._extract_people(call):
                key = name.casefold()
                entry = people.setdefault(
                    key,
                    {"id": str(uuid5(NAMESPACE_URL, f"tca-person:{key}")), "name": name, "calls": set()},
                )
                entry["calls"].add(call.id)

        result = [
            Person(
                id=entry["id"],
                name=entry["name"],
                conversation_count=len(entry["calls"]),
            )
            for entry in people.values()
        ]
        result.sort(key=lambda person: (-person.conversation_count, person.name.casefold()))
        return result

    def get_person_detail(
        self,
        person_id: str,
    ) -> PersonDetail | None:
        matches: list[
            tuple[Call, str]
        ] = []

        for call in self.list_all():
            for name in self._extract_people(call):
                candidate_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        f"tca-person:{name.casefold()}",
                    )
                )

                if candidate_id == person_id:
                    matches.append(
                        (call, name)
                    )
                    break

        if not matches:
            return None

        person_name = matches[0][1]

        conversations = [
            call
            for call, _ in matches
        ]

        open_steps: list[
            PersonTask
        ] = []

        decisions: list[
            str
        ] = []

        for call in conversations:
            tasks = self.get_tasks(
                call.id
            )

            # Any open "their" task from a
            # conversation associated with
            # this person belongs in their
            # People memory for now.
            for task in tasks:
                if (
                    task.completed
                    or task.owner
                    != TaskOwner.THEM
                ):
                    continue

                open_steps.append(
                    PersonTask(
                        id=task.id,
                        call_id=task.call_id,
                        task=task.task,
                        deadline=task.deadline,
                        completed=task.completed,
                    )
                )

            notes_file = (
                self._call_directory(
                    call.id
                )
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

                raw_decisions = notes.get(
                    "decisions",
                    [],
                )

                if isinstance(
                    raw_decisions,
                    list,
                ):
                    for item in raw_decisions:
                        if isinstance(
                            item,
                            dict,
                        ):
                            value = str(
                                item.get(
                                    "decision",
                                    "",
                                )
                                or ""
                            ).strip()
                        else:
                            value = str(
                                item or ""
                            ).strip()

                        if (
                            value
                            and value
                            not in decisions
                        ):
                            decisions.append(
                                value
                            )

        return PersonDetail(
            id=person_id,
            name=person_name,
            conversation_count=len(
                conversations
            ),
            open_next_steps=open_steps,
            recent_decisions=decisions[:8],
            conversations=conversations,
        )

    def _extract_people(self, call: Call) -> list[str]:
        """
        Prefer structured participant memory produced by the
        V0.4 processing pipeline. Keep the deterministic V3
        extraction as a compatibility fallback for older calls.
        """
        call_directory = self._call_directory(call.id)

        notes_file = call_directory / "notes.json"
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

            structured_names: list[str] = []
            participants = notes.get(
                "participants",
                [],
            )

            if isinstance(
                participants,
                list,
            ):
                for participant in participants:
                    if not isinstance(
                        participant,
                        dict,
                    ):
                        continue

                    role = str(
                        participant.get(
                            "role",
                            "",
                        )
                        or ""
                    ).casefold()

                    name = str(
                        participant.get(
                            "name",
                            "",
                        )
                        or ""
                    ).strip()

                    if (
                        role == "them"
                        and name
                        and self._is_plausible_person_name(
                            name
                        )
                    ):
                        structured_names.append(
                            name
                        )

            if structured_names:
                return list(
                    dict.fromkeys(
                        structured_names
                    )
                )

        return self._extract_people_legacy(
            call
        )

    def _extract_people_legacy(
        self,
        call: Call,
    ) -> list[str]:
        call_directory = self._call_directory(call.id)
        texts = [call.title]

        notes_file = call_directory / "notes.json"
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

            texts.extend(
                self._flatten_person_text(
                    notes
                )
            )

        transcript_file = (
            call_directory
            / "combined_transcript.txt"
        )

        if transcript_file.exists():
            try:
                texts.append(
                    transcript_file.read_text(
                        encoding="utf-8"
                    )
                )
            except OSError:
                pass

        found: dict[str, str] = {}
        patterns = [
            r"\bwith\s+([A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30})?)",
            r"\b(?:thank you so much,|thanks,|hello,|hi,)\s*([A-Z][a-z]{1,30})\b",
            r"\b([A-Z][a-z]{1,30})\s+(?:said|noted|will|agreed|highlighted|committed|mentioned)\b",
            r"\b([A-Z][a-z]{1,30})\s+(?:is|was)\s+the\s+(?:one|person)\b",
        ]

        excluded = self._excluded_person_names()

        for text in texts:
            for pattern in patterns:
                for match in re.finditer(
                    pattern,
                    text,
                ):
                    name = match.group(1).strip()

                    if (
                        name in excluded
                        or len(name) < 2
                    ):
                        continue

                    if not self._is_plausible_person_name(
                        name
                    ):
                        continue

                    key = name.casefold()
                    found.setdefault(
                        key,
                        name,
                    )

        return list(
            found.values()
        )

    def _is_plausible_person_name(
        self,
        name: str,
    ) -> bool:
        cleaned = (
            " ".join(
                name.strip().split()
            )
        )

        if not cleaned:
            return False

        if any(
            character.isdigit()
            for character in cleaned
        ):
            return False

        if any(
            part in self._excluded_person_names()
            for part in cleaned.split()
        ):
            return False

        return bool(
            re.fullmatch(
                r"[A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30})?",
                cleaned,
            )
        )

    def _excluded_person_names(self) -> set[str]:
        return {
            "Wednesday", "Thursday", "Friday",
            "Monday", "Tuesday", "Saturday",
            "Sunday", "January", "February",
            "March", "April", "May", "June",
            "July", "August", "September",
            "October", "November", "December",
            "Android", "WhatsApp", "TCA",
            "Then", "They", "The", "This",
            "That", "These", "Those",
            "Me", "Them", "Remote", "Local",
            "Speaker", "Call", "Conversation",
        }

    def _flatten_person_text(self, value) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                result.extend(self._flatten_person_text(item))
            return result
        if isinstance(value, dict):
            result: list[str] = []
            for item in value.values():
                result.extend(self._flatten_person_text(item))
            return result
        return []

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