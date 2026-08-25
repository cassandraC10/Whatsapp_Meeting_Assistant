import json
import os
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

    deadline: str | None = Field(
        default=None,
        description=(
            "Deadline if clearly mentioned. "
            "Otherwise null."
        ),
    )


class Decision(BaseModel):
    decision: str = Field(
        description=(
            "A decision clearly reached "
            "during the conversation."
        )
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


def generate_conversation_notes(
    transcript: str,
    status_callback=None,
) -> ConversationNotes:
    if not transcript.strip():
        raise RuntimeError(
            "A transcript is required "
            "before notes can be generated."
        )

    prompt = f"""
You are creating useful notes from a real conversation.

The transcript contains two participants:

ME / LOCAL SPEAKER
= the person using TCA.

THEM / REMOTE SPEAKER
= the other person on the call. They may be a client,
friend, colleague, recruiter, collaborator, family member
or anyone else.

Create concise notes from the WHOLE conversation.

Rules:

- Do not invent anything.
- Do not focus only on business topics.
- Capture meaningful feedback, opinions, concerns,
  suggestions and context inside key_points.
- Keep casual small talk out unless it adds useful context.
- Do not force action items.
- Do not force decisions.
- Do not force dates.
- Do not force follow-up.
- Empty lists are completely acceptable.
- Keep action ownership correct.
- Do not assume someone accepted a task unless the
  transcript supports it.
- Preserve names, dates, amounts, preferences and
  meaningful personal details accurately.
- Keep relative dates such as "tomorrow" as spoken unless
  the transcript clearly establishes the calendar date.
- Avoid duplicates.
- Keep the result natural and useful after the call.

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

    return (
        ConversationNotes
        .model_validate_json(
            response.text
        )
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

IMPORTANT DATES
{format_list(notes.important_dates)}

FOLLOW-UP
{notes.follow_up or "None."}
""".strip()


def summarize_call(
    call_directory: str | Path,
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
        "V2 notes are call-specific. "
        "Run them through the TCA backend."
    )