import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found. "
        "Add GEMINI_API_KEY=your_key_here to your .env file."
    )

client = genai.Client(api_key=API_KEY)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSCRIPT_FILE = PROJECT_ROOT / "combined_transcript.txt"
JSON_OUTPUT_FILE = PROJECT_ROOT / "meeting_notes.json"
TEXT_OUTPUT_FILE = PROJECT_ROOT / "meeting_notes.txt"

MODEL_NAME = "gemini-3.5-flash"

MAX_RETRIES = 4
RETRY_DELAYS = [2, 4, 8]


class ActionItem(BaseModel):
    task: str = Field(
        description="A task or next step clearly assigned to this speaker."
    )

    deadline: str | None = Field(
        default=None,
        description=(
            "The deadline for this task if one was clearly stated. "
            "Otherwise return null."
        ),
    )


class Decision(BaseModel):
    decision: str = Field(
        description="A decision clearly reached during the conversation."
    )


class MeetingNotes(BaseModel):
    title: str = Field(
        description="A short, natural title for the conversation."
    )

    summary: str = Field(
        description=(
            "A concise summary of the whole conversation, including the "
            "most meaningful practical or personal context."
        )
    )

    key_points: list[str] = Field(
        description=(
            "The most useful points from the conversation. Include meaningful "
            "feedback, opinions, concerns, suggestions and context here."
        )
    )

    decisions: list[Decision] = Field(
        description="Decisions clearly reached during the conversation."
    )

    my_action_items: list[ActionItem] = Field(
        description="Next steps belonging to ME / LOCAL SPEAKER."
    )

    client_action_items: list[ActionItem] = Field(
        description=(
            "Next steps belonging to CLIENT / REMOTE SPEAKER. "
            "The remote speaker may be a friend, client, colleague or anyone else."
        )
    )

    deadlines: list[str] = Field(
        description=(
            "Important dates or time references that genuinely matter "
            "to the conversation."
        )
    )

    follow_up: str | None = Field(
        default=None,
        description=(
            "A clearly agreed follow-up or next contact. "
            "Return null if none was agreed."
        ),
    )


def is_daily_quota_error(error):
    message = str(error).lower()

    markers = [
        "requestsperday",
        "perdayperproject",
        "generate requests per day",
    ]

    return any(marker in message for marker in markers)


def is_temporary_gemini_error(error):
    message = str(error).lower()

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

    return any(marker in message for marker in markers)


def generate_notes_with_retry(
    prompt,
    config,
    status_callback=None,
):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
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

            if is_daily_quota_error(error):
                raise RuntimeError(
                    "Daily Gemini free-tier limit reached. "
                    "Your recording is safe. Try again after the quota resets."
                ) from error

            if not is_temporary_gemini_error(error):
                raise

            if attempt >= MAX_RETRIES:
                break

            delay = RETRY_DELAYS[attempt - 1]

            message = (
                f"Service is busy. Trying again in "
                f"{delay} seconds..."
            )

            print(message)

            if status_callback:
                status_callback(message)

            time.sleep(delay)

    raise RuntimeError(
        "The notes could not be completed after several attempts. "
        f"Last error: {last_error}"
    )


def load_transcript():
    if not TRANSCRIPT_FILE.exists():
        raise FileNotFoundError(
            f"Transcript not found: {TRANSCRIPT_FILE}"
        )

    transcript = TRANSCRIPT_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not transcript:
        raise RuntimeError(
            "combined_transcript.txt is empty."
        )

    return transcript


def generate_meeting_notes(
    transcript,
    status_callback=None,
):
    prompt = f"""
You are a conversation notes assistant.

The transcript contains two identified participants:

ME / LOCAL SPEAKER
= the person using this app.

CLIENT / REMOTE SPEAKER
= the other person on the call. They may be a friend,
client, colleague, family member or anyone else.

Create useful notes from the WHOLE conversation.

Rules:

- Do not invent anything.
- Do not focus only on business or deadlines.
- Capture meaningful personal feedback, opinions,
  concerns and suggestions inside key_points.
- Keep casual small talk out unless it adds useful context.
- Do not force action items, decisions, dates or follow-up.
- Empty sections are completely acceptable.
- Keep action items assigned to the correct person.
- Do not assume someone accepted a task unless the
  conversation clearly supports it.
- Preserve names, dates, feelings, preferences,
  amounts and important details accurately.
- Keep relative dates such as "tomorrow" or "Friday"
  as spoken unless the transcript establishes the
  exact calendar date.
- Avoid duplicates.
- Keep everything concise, natural and useful.

TRANSCRIPT:

{transcript}
"""

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=MeetingNotes,
    )

    response = generate_notes_with_retry(
        prompt=prompt,
        config=config,
        status_callback=status_callback,
    )

    if not response.text:
        raise RuntimeError(
            "No notes were returned."
        )

    return MeetingNotes.model_validate_json(
        response.text
    )


def save_json(notes):
    JSON_OUTPUT_FILE.write_text(
        json.dumps(
            notes.model_dump(),
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved {JSON_OUTPUT_FILE.name}"
    )


def format_list(items):
    if not items:
        return "None."

    return "\n".join(
        f"- {item}"
        for item in items
    )


def format_decisions(items):
    if not items:
        return "None."

    return "\n".join(
        f"- {item.decision}"
        for item in items
    )


def format_action_items(items):
    if not items:
        return "None."

    lines = []

    for item in items:
        line = f"- {item.task}"

        if item.deadline:
            line += f" (Due: {item.deadline})"

        lines.append(line)

    return "\n".join(lines)


def create_text_notes(notes):
    return f"""
CONVERSATION NOTES

TITLE
{notes.title}

SUMMARY
{notes.summary}

KEY POINTS
{format_list(notes.key_points)}

MY NEXT STEPS
{format_action_items(notes.my_action_items)}

THEIR NEXT STEPS
{format_action_items(notes.client_action_items)}

DECISIONS
{format_decisions(notes.decisions)}

IMPORTANT DATES
{format_list(notes.deadlines)}

FOLLOW-UP
{notes.follow_up or "None."}
""".strip()


def save_text_notes(text):
    TEXT_OUTPUT_FILE.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"Saved {TEXT_OUTPUT_FILE.name}"
    )


def summarize_meeting(
    status_callback=None,
):
    print("\nConversation Notes\n")

    if status_callback:
        status_callback(
            "Reading your conversation..."
        )

    transcript = load_transcript()

    if status_callback:
        status_callback(
            "Pulling out the important parts..."
        )

    notes = generate_meeting_notes(
        transcript,
        status_callback=status_callback,
    )

    if status_callback:
        status_callback(
            "Saving your notes..."
        )

    save_json(notes)

    text_notes = create_text_notes(
        notes
    )

    save_text_notes(
        text_notes
    )

    print("\nSUCCESS\n")
    print(text_notes)

    return notes, text_notes


if __name__ == "__main__":
    summarize_meeting()