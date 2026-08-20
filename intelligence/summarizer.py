import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found.\n"
        "Make sure your .env file contains:\n"
        "GEMINI_API_KEY=your_key_here"
    )


client = genai.Client(api_key=API_KEY)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TRANSCRIPT_FILE = PROJECT_ROOT / "combined_transcript.txt"

JSON_OUTPUT_FILE = PROJECT_ROOT / "meeting_notes.json"

TEXT_OUTPUT_FILE = PROJECT_ROOT / "meeting_notes.txt"


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = "gemini-3.5-flash"


# ============================================================
# RETRY CONFIG
# ============================================================

MAX_RETRIES = 4

RETRY_DELAYS = [
    2,
    4,
    8,
]


# ============================================================
# STRUCTURED DATA MODELS
# ============================================================


class ActionItem(BaseModel):

    task: str = Field(
        description=(
            "The exact task or responsibility " "that was agreed during the meeting."
        )
    )

    deadline: str | None = Field(
        default=None,
        description=(
            "The deadline mentioned in the meeting. "
            "Use null if no deadline was explicitly stated."
        ),
    )


class Decision(BaseModel):

    decision: str = Field(
        description=("A decision that was actually agreed " "during the meeting.")
    )


class MeetingNotes(BaseModel):

    title: str = Field(description=("A concise descriptive title " "for the meeting."))

    summary: str = Field(
        description=(
            "A concise summary of what the meeting " "was about and its main outcome."
        )
    )

    key_points: list[str] = Field(
        description=(
            "Important topics, facts, concerns, "
            "or discussion points from the meeting."
        )
    )

    decisions: list[Decision] = Field(
        description=("Decisions explicitly made or agreed " "during the meeting.")
    )

    my_action_items: list[ActionItem] = Field(
        description=("Tasks explicitly belonging to " "ME / LOCAL SPEAKER.")
    )

    client_action_items: list[ActionItem] = Field(
        description=("Tasks explicitly belonging to " "CLIENT / REMOTE SPEAKER.")
    )

    deadlines: list[str] = Field(
        description=(
            "Explicit deadlines or dates mentioned "
            "in relation to actions or deliverables."
        )
    )

    follow_up: str | None = Field(
        default=None,
        description=(
            "Any explicitly agreed follow-up meeting, "
            "date, time, or next-step arrangement. "
            "Use null if none was stated."
        ),
    )


# ============================================================
# TEMPORARY GEMINI ERROR DETECTION
# ============================================================


def is_temporary_gemini_error(error):
    """
    Returns True for temporary errors that are
    worth retrying.
    """

    message = str(error).lower()

    temporary_markers = [
        "503",
        "unavailable",
        "high demand",
        "429",
        "resource exhausted",
        "temporarily",
        "timeout",
        "deadline exceeded",
    ]

    return any(marker in message for marker in temporary_markers)


# ============================================================
# GEMINI RETRY WRAPPER
# ============================================================


def generate_notes_with_retry(
    prompt,
    config,
    status_callback=None,
):
    """
    Calls Gemini and automatically retries
    temporary errors such as 503 or 429.
    """

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(f"Gemini notes attempt " f"{attempt}/{MAX_RETRIES}...")

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

            return response

        except Exception as error:

            last_error = error

            if not is_temporary_gemini_error(error):
                raise

            if attempt >= MAX_RETRIES:
                break

            delay = RETRY_DELAYS[attempt - 1]

            message = (
                "Gemini is busy while generating "
                f"meeting notes. Retrying in "
                f"{delay} seconds "
                f"({attempt}/{MAX_RETRIES})..."
            )

            print(message)

            if status_callback:
                status_callback(message)

            time.sleep(delay)

    raise RuntimeError(
        "Gemini could not generate meeting notes "
        "after multiple retries.\n"
        f"Last error: {last_error}"
    )


# ============================================================
# LOAD TRANSCRIPT
# ============================================================


def load_transcript():

    if not TRANSCRIPT_FILE.exists():

        raise FileNotFoundError(f"Transcript not found:\n" f"{TRANSCRIPT_FILE}")

    transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8").strip()

    if not transcript:

        raise RuntimeError("combined_transcript.txt is empty.")

    return transcript


# ============================================================
# GENERATE MEETING INTELLIGENCE
# ============================================================


def generate_meeting_notes(
    transcript,
    status_callback=None,
):

    print()
    print("Analyzing meeting transcript...")

    prompt = f"""
You are an AI meeting assistant.

You are given a business meeting transcript with
two clearly identified participants:

ME / LOCAL SPEAKER
= the user of the meeting assistant.

CLIENT / REMOTE SPEAKER
= the other participant on the call.

Your job is to analyze the meeting and extract
ONLY information supported by the transcript.

CRITICAL RULES:

1. Do not invent information.

2. Do not invent deadlines.

3. Do not invent action items.

4. Do not infer that someone accepted a task unless
   the transcript reasonably shows that they did.

5. Keep tasks assigned to the correct speaker.

6. Anything said by ME / LOCAL SPEAKER belongs to
   the user.

7. Anything said by CLIENT / REMOTE SPEAKER belongs
   to the client.

8. If no decisions were made, return an empty list.

9. If no action items exist for one participant,
   return an empty list.

10. If no deadline was stated, use null for the
    action item's deadline.

11. Do not turn casual conversation into an
    action item.

12. Preserve important names, dates, amounts,
    deliverables, and business terms accurately.

13. "Tomorrow", "Friday", "next week", etc. should
    remain exactly as expressed unless the transcript
    itself establishes the absolute date.

14. The summary should be concise and useful after
    the meeting.

15. Avoid duplicate action items or deadlines.


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

        raise RuntimeError("Gemini returned an empty response.")

    notes = MeetingNotes.model_validate_json(response.text)

    return notes


# ============================================================
# SAVE JSON
# ============================================================


def save_json(notes):

    data = notes.model_dump()

    with open(
        JSON_OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(f"Saved structured notes: " f"{JSON_OUTPUT_FILE.name}")


# ============================================================
# FORMATTING HELPERS
# ============================================================


def format_action_items(items):

    if not items:
        return "None."

    lines = []

    for item in items:

        if item.deadline:

            lines.append(f"- {item.task} " f"(Deadline: {item.deadline})")

        else:

            lines.append(f"- {item.task}")

    return "\n".join(lines)


def format_list(items):

    if not items:
        return "None."

    return "\n".join(f"- {item}" for item in items)


def format_decisions(decisions):

    if not decisions:
        return "None."

    return "\n".join(f"- {item.decision}" for item in decisions)


# ============================================================
# HUMAN READABLE NOTES
# ============================================================


def create_text_notes(notes):

    text = f"""
============================================================
MEETING NOTES
============================================================

TITLE
{notes.title}


SUMMARY
{notes.summary}


KEY DISCUSSION POINTS
{format_list(notes.key_points)}


DECISIONS
{format_decisions(notes.decisions)}


MY ACTION ITEMS
{format_action_items(notes.my_action_items)}


CLIENT ACTION ITEMS
{format_action_items(notes.client_action_items)}


DEADLINES
{format_list(notes.deadlines)}


FOLLOW-UP
{notes.follow_up if notes.follow_up else "None."}

============================================================
""".strip()

    return text


# ============================================================
# SAVE TEXT
# ============================================================


def save_text_notes(text):

    with open(
        TEXT_OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(text)

    print(f"Saved readable notes: " f"{TEXT_OUTPUT_FILE.name}")


# ============================================================
# MAIN
# ============================================================


def summarize_meeting(
    status_callback=None,
):

    print()
    print("========================================")
    print("       AI Meeting Intelligence")
    print("========================================")

    print()

    print(f"Model: {MODEL_NAME}")

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    print()
    print("STEP 1/3 — Loading transcript")

    if status_callback:

        status_callback("Loading meeting transcript...")

    transcript = load_transcript()

    print(f"Loaded {len(transcript)} characters.")

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    print()
    print("STEP 2/3 — Generating meeting intelligence")

    if status_callback:

        status_callback("Generating meeting notes...")

    notes = generate_meeting_notes(
        transcript,
        status_callback=status_callback,
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    print()
    print("STEP 3/3 — Saving meeting notes")

    if status_callback:

        status_callback("Saving meeting notes...")

    save_json(notes)

    text_notes = create_text_notes(notes)

    save_text_notes(text_notes)

    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    print()
    print("========================================")
    print("               SUCCESS")
    print("========================================")

    print()

    print(text_notes)

    print()

    return (
        notes,
        text_notes,
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    summarize_meeting()
