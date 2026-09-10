import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


load_dotenv()

API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found. "
        "Add it to your .env file."
    )

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash",
)

MAX_RETRIES = 4
RETRY_DELAYS = [2, 4, 8]

client = genai.Client(
    api_key=API_KEY
)


class ActionItem(BaseModel):
    task: str = Field(
        description=(
            "A next step clearly belonging "
            "to this person."
        )
    )

    deadline: str = Field(
        description=(
            "A grounded deadline explicitly stated or "
            "unambiguously established in the conversation. "
            "Every action item must have one."
        ),
    )

    owner_name: str | None = Field(
        default=None,
        description=(
            "The person's name only when it is "
            "explicitly known from the supplied context "
            "or transcript. Otherwise null."
        ),
    )


class Decision(BaseModel):
    decision: str = Field(
        description=(
            "A decision clearly reached "
            "during the conversation."
        )
    )


class Participant(BaseModel):
    role: str = Field(
        description=(
            "Either 'me' or 'them'."
        )
    )

    name: str | None = Field(
        default=None,
        description=(
            "Known participant name. Null when "
            "the identity is not established."
        ),
    )

    source: str | None = Field(
        default=None,
        description=(
            "Evidence source such as call-title, "
            "transcript, or null."
        ),
    )


class ConversationNotes(BaseModel):
    title: str = Field(
        description=(
            "A short natural title for "
            "the conversation."
        )
    )

    summary: str = Field(
        description=(
            "A concise summary of the whole "
            "conversation."
        )
    )

    participants: list[Participant] = Field(
        default_factory=list,
        description=(
            "The two conversation participants. "
            "Use the supplied participant context when "
            "available. Never invent a person's identity."
        ),
    )

    key_points: list[str] = Field(
        description=(
            "Important facts, feedback, opinions, "
            "concerns, suggestions or context."
        )
    )

    decisions: list[Decision] = Field(
        description=(
            "Decisions actually made."
        )
    )

    my_action_items: list[ActionItem] = Field(
        description=(
            "Next steps belonging to "
            "ME / LOCAL SPEAKER."
        )
    )

    their_action_items: list[ActionItem] = Field(
        description=(
            "Next steps belonging to "
            "THEM / REMOTE SPEAKER."
        )
    )

    important_dates: list[str] = Field(
        description=(
            "Important dates or time references "
            "actually mentioned."
        )
    )

    follow_up: str | None = Field(
        default=None,
        description=(
            "Agreed follow-up if one exists. "
            "Otherwise null."
        ),
    )


def is_daily_quota_error(
    error,
) -> bool:
    message = str(
        error
    ).lower()

    markers = [
        "requestsperday",
        "perdayperproject",
        "generate requests per day",
    ]

    return any(
        marker in message
        for marker in markers
    )


def is_temporary_gemini_error(
    error,
) -> bool:
    message = str(
        error
    ).lower()

    markers = [
        "503",
        "unavailable",
        "high demand",
        "429",
        "resource exhausted",
        "temporarily",
        "timeout",
        "deadline exceeded",
    ]

    return any(
        marker in message
        for marker in markers
    )


def generate_notes_with_retry(
    prompt,
    config,
    status_callback=None,
):
    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            print(
                f"Gemini notes attempt "
                f"{attempt}/{MAX_RETRIES}..."
            )

            return client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

        except Exception as error:
            last_error = error

            if is_daily_quota_error(
                error
            ):
                raise RuntimeError(
                    "Daily Gemini quota reached. "
                    "Your transcript is safe. "
                    "Try again after the quota resets."
                ) from error

            if not is_temporary_gemini_error(
                error
            ):
                raise

            if attempt >= MAX_RETRIES:
                break

            delay = RETRY_DELAYS[
                attempt - 1
            ]

            message = (
                f"Notes service is busy. "
                f"Trying again in {delay} seconds..."
            )

            print(message)

            if status_callback:
                status_callback(message)

            time.sleep(delay)

    raise RuntimeError(
        "Notes could not be generated "
        "after several attempts. "
        f"Last error: {last_error}"
    )


def _clean_known_name(
    name: str | None,
) -> str | None:
    if not name:
        return None

    cleaned = (
        " ".join(
            str(name).strip().split()
        )
    )

    if not cleaned:
        return None

    return cleaned


def _participant_from_context(
    remote_participant_name: str | None,
) -> list[dict]:
    return [
        {
            "role": "me",
            "name": None,
            "source": "local-speaker",
        },
        {
            "role": "them",
            "name": (
                _clean_known_name(
                    remote_participant_name
                )
            ),
            "source": (
                "call-title"
                if remote_participant_name
                else None
            ),
        },
    ]


def _name_appears_in_text(
    name: str,
    transcript: str,
) -> bool:
    parts = [
        re.escape(
            part
        )
        for part in name.split()
    ]

    pattern = (
        r"\b"
        + r"\s+".join(parts)
        + r"\b"
    )

    return bool(
        re.search(
            pattern,
            transcript,
            flags=re.IGNORECASE,
        )
    )


def _normalise_date_text(
    value: str,
) -> str:
    return (
        " ".join(
            value.strip().casefold().split()
        )
        .replace("–", "-")
        .replace("—", "-")
    )


def _filter_undated_action_items(
    notes: ConversationNotes,
) -> None:
    notes.my_action_items = [
        item
        for item in notes.my_action_items
        if item.deadline
        and item.deadline.strip()
    ]

    notes.their_action_items = [
        item
        for item in notes.their_action_items
        if item.deadline
        and item.deadline.strip()
    ]


def _filter_other_timing(
    notes: ConversationNotes,
) -> None:
    action_deadlines = {
        _normalise_date_text(item.deadline)
        for item in (
            notes.my_action_items
            + notes.their_action_items
        )
        if item.deadline
        and item.deadline.strip()
    }

    filtered: list[str] = []

    for value in notes.important_dates:
        cleaned = str(value or "").strip()

        if not cleaned:
            continue

        if (
            _normalise_date_text(cleaned)
            in action_deadlines
        ):
            continue

        if cleaned not in filtered:
            filtered.append(cleaned)

    notes.important_dates = filtered


def _sanitize_notes(
    notes: ConversationNotes,
    transcript: str,
    call_title: str | None,
    remote_participant_name: str | None,
) -> ConversationNotes:
    known_name = _clean_known_name(
        remote_participant_name
    )

    participants = (
        _participant_from_context(
            known_name
        )
    )

    # A name supplied by the call title is authoritative.
    # We never replace it with a model guess.
    if known_name:
        notes.participants = [
            Participant(
                role="me",
                name=None,
                source="local-speaker",
            ),
            Participant(
                role="them",
                name=known_name,
                source="call-title",
            ),
        ]
    else:
        # Without explicit identity context, only retain model
        # names that are visibly present in the transcript.
        safe_participants: list[Participant] = [
            Participant(
                role="me",
                name=None,
                source="local-speaker",
            )
        ]

        for participant in notes.participants:
            role = (
                str(
                    participant.role
                    or ""
                ).casefold()
            )

            candidate = _clean_known_name(
                participant.name
            )

            if (
                role != "them"
                or not candidate
                or not _name_appears_in_text(
                    candidate,
                    transcript,
                )
            ):
                continue

            safe_participants.append(
                Participant(
                    role="them",
                    name=candidate,
                    source="transcript",
                )
            )
            break

        if len(safe_participants) == 1:
            safe_participants.append(
                Participant(
                    role="them",
                    name=None,
                    source=None,
                )
            )

        notes.participants = safe_participants

    effective_remote_name = (
        known_name
        or next(
            (
                participant.name
                for participant in notes.participants
                if (
                    participant.role.casefold()
                    == "them"
                    and participant.name
                )
            ),
            None,
        )
    )

    sanitized_their_items: list[ActionItem] = []

    for item in notes.their_action_items:
        item.owner_name = (
            effective_remote_name
        )
        sanitized_their_items.append(
            item
        )

    notes.their_action_items = (
        sanitized_their_items
    )

    for item in notes.my_action_items:
        item.owner_name = None

    # The title generated by the model should not erase a useful
    # explicit call title. We only fall back when the model returns
    # an empty title.
    if not notes.title.strip():
        notes.title = (
            call_title.strip()
            if call_title
            and call_title.strip()
            else "Untitled call"
        )

    _filter_undated_action_items(notes)
    _filter_other_timing(notes)

    return notes


def generate_conversation_notes(
    transcript: str,
    call_title: str | None = None,
    remote_participant_name: str | None = None,
    status_callback=None,
) -> ConversationNotes:
    if not transcript.strip():
        raise RuntimeError(
            "A transcript is required "
            "before notes can be generated."
        )

    known_name = _clean_known_name(
        remote_participant_name
    )

    context_lines = [
        "CALL CONTEXT:",
        (
            f"Call title: {call_title.strip()}"
            if call_title
            and call_title.strip()
            else "Call title: not provided."
        ),
        "Speaker roles:",
        (
            "ME = local TCA user."
        ),
        (
            f"THEM = {known_name}. "
            "This identity is explicitly supplied by "
            "the call title and must be preserved."
            if known_name
            else
            "THEM = remote speaker. "
            "Their name is unknown unless the transcript "
            "clearly establishes it."
        ),
        "",
    ]

    prompt = f"""
You are creating useful memory from a real conversation.

{chr(10).join(context_lines)}

Create concise notes from the WHOLE conversation.

Grounding rules:

- The transcript is the source of truth for what was said.
- The supplied call context is the source of truth for known
  participant identity.
- Never invent a participant name.
- Never turn generic words such as "they", "then", "the",
  "this", "that", weekdays or months into people.
- If the remote participant name is unknown, leave it null.
- When the remote participant name is known, use that exact name
  when referring to THEM in summary, key points, decisions or
  action items. Do not replace a known person's name with
  "they", "them", "the speaker" or another invented label.
- Never invent a decision.
- Never invent a task.
- Never invent a deadline.
- Never infer agreement when the transcript does not support it.
- Preserve names, dates, amounts, preferences and meaningful
  personal details accurately.
- Keep relative dates such as "tomorrow" as spoken unless the
  transcript clearly establishes the calendar date.
- Avoid duplicates.
- Empty lists are completely acceptable.

Conversation quality rules:

- Do not focus only on business topics.
- Capture meaningful feedback, opinions, concerns, suggestions
  and useful context inside key_points.
- Keep casual small talk out unless it adds useful context.
- Keep action ownership correct.
- A task belongs in my_action_items only when it clearly belongs
  to ME.
- A task belongs in their_action_items only when it clearly
  belongs to THEM.
- Do not force decisions or follow-up.
- Every returned action item must have a grounded deadline.
- If an action has no grounded deadline, do not return it as an
  action item.
- Put the deadline on the action item itself.
- Do not repeat action-item deadlines in important_dates.

Participant rules:

- Always return a participant entry for ME.
- Always return a participant entry for THEM.
- For THEM, use the supplied name if one is explicitly provided.
- Otherwise use null unless the transcript itself clearly
  establishes a person's name.
- For every non-null participant name, provide a truthful source.

TRANSCRIPT:

{transcript}
"""

    config = types.GenerateContentConfig(
        response_mime_type=(
            "application/json"
        ),
        response_schema=(
            ConversationNotes
        ),
    )

    response = generate_notes_with_retry(
        prompt=prompt,
        config=config,
        status_callback=status_callback,
    )

    if not response.text:
        raise RuntimeError(
            "No conversation notes were returned."
        )

    notes = (
        ConversationNotes
        .model_validate_json(
            response.text
        )
    )

    return _sanitize_notes(
        notes=notes,
        transcript=transcript,
        call_title=call_title,
        remote_participant_name=(
            remote_participant_name
        ),
    )


def format_list(
    items: list[str],
) -> str:
    if not items:
        return "None."

    return "\n".join(
        f"- {item}"
        for item in items
    )


def format_decisions(
    decisions: list[Decision],
) -> str:
    if not decisions:
        return "None."

    return "\n".join(
        f"- {item.decision}"
        for item in decisions
    )


def format_action_items(
    items: list[ActionItem],
) -> str:
    if not items:
        return "None."

    lines = []

    for item in items:
        line = f"- {item.task}"

        if item.owner_name:
            line = (
                f"- {item.owner_name}: "
                f"{item.task}"
            )

        if item.deadline:
            line += (
                f" (Due: {item.deadline})"
            )

        lines.append(line)

    return "\n".join(lines)


def create_text_notes(
    notes: ConversationNotes,
) -> str:
    return f"""
TCA — THE CALL ASSISTANT

{notes.title}

PARTICIPANTS
{format_list([
    (
        f"{item.role}: {item.name}"
        if item.name
        else item.role
    )
    for item in notes.participants
])}

SUMMARY
{notes.summary}

KEY POINTS
{format_list(notes.key_points)}

MY NEXT STEPS
{format_action_items(notes.my_action_items)}

THEIR NEXT STEPS
{format_action_items(notes.their_action_items)}

DECISIONS
{format_decisions(notes.decisions)}

{"OTHER TIMING" if notes.important_dates else ""}
{format_list(notes.important_dates) if notes.important_dates else ""}

FOLLOW-UP
{notes.follow_up or "None."}
""".strip()


def summarize_call(
    call_directory: str | Path,
    call_title: str | None = None,
    remote_participant_name: str | None = None,
    status_callback=None,
) -> tuple[
    ConversationNotes,
    str,
]:
    call_directory = Path(
        call_directory
    )

    transcript_file = (
        call_directory
        / "combined_transcript.txt"
    )

    if not transcript_file.exists():
        raise RuntimeError(
            "No transcript exists for this call. "
            "Notes cannot be generated."
        )

    transcript = (
        transcript_file
        .read_text(
            encoding="utf-8"
        )
        .strip()
    )

    if not transcript:
        raise RuntimeError(
            "The transcript is empty. "
            "Notes cannot be generated."
        )

    if status_callback:
        status_callback(
            "Organising your notes..."
        )

    notes = generate_conversation_notes(
        transcript=transcript,
        call_title=call_title,
        remote_participant_name=(
            remote_participant_name
        ),
        status_callback=status_callback,
    )

    notes_json_file = (
        call_directory
        / "notes.json"
    )

    notes_text_file = (
        call_directory
        / "notes.txt"
    )

    notes_json_file.write_text(
        json.dumps(
            notes.model_dump(),
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    text_notes = (
        create_text_notes(
            notes
        )
    )

    notes_text_file.write_text(
        text_notes,
        encoding="utf-8",
    )

    print(
        f"Saved notes to: "
        f"{notes_json_file}"
    )

    return (
        notes,
        text_notes,
    )


if __name__ == "__main__":
    raise SystemExit(
        "V0.4 notes are call-specific. "
        "Run them through the TCA backend."
    )
