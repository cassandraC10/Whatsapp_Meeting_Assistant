import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from google import genai


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


def validate_audio_file(
    audio_path: Path,
) -> None:
    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    if audio_path.stat().st_size == 0:
        raise RuntimeError(
            f"Audio file is empty: {audio_path}"
        )


def generate_with_retry(
    contents,
    status_callback=None,
):
    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            print(
                f"Gemini transcription attempt "
                f"{attempt}/{MAX_RETRIES}..."
            )

            return client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
            )

        except Exception as error:
            last_error = error

            if is_daily_quota_error(
                error
            ):
                raise RuntimeError(
                    "Daily Gemini quota reached. "
                    "Your recording is safe. "
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
                f"Transcription service is busy. "
                f"Trying again in {delay} seconds..."
            )

            print(message)

            if status_callback:
                status_callback(message)

            time.sleep(delay)

    raise RuntimeError(
        "Transcription failed after several attempts. "
        f"Last error: {last_error}"
    )


def _excluded_person_name_parts() -> set[str]:
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


def _is_plausible_person_name(
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
        part in _excluded_person_name_parts()
        for part in cleaned.split()
    ):
        return False

    return bool(
        re.fullmatch(
            r"[A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30})?",
            cleaned,
        )
    )


def infer_remote_participant_name(
    call_title: str | None,
) -> str | None:
    """
    Extract a remote participant only when the call title gives
    explicit evidence, such as "with Jose" or "- Jose".

    The marker word itself is matched case-insensitively because the
    title is user-entered. The captured name is normalized only when
    the user typed it in lowercase; otherwise its original casing is
    preserved.
    """
    if not call_title:
        return None

    title = " ".join(
        call_title.strip().split()
    )

    patterns = [
        r"\bwith\s+([A-Za-z][A-Za-z'’-]{1,30}(?:\s+[A-Za-z][A-Za-z'’-]{1,30})?)\s*$",
        r"[-–—]\s*([A-Za-z][A-Za-z'’-]{1,30}(?:\s+[A-Za-z][A-Za-z'’-]{1,30})?)\s*$",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            title,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(1).strip(
            " .,:;!?-–—"
        )

        if not candidate:
            continue

        if candidate.islower():
            candidate = candidate.title()

        if _is_plausible_person_name(
            candidate
        ):
            return candidate

    return None

def transcribe_audio(
    audio_path: Path,
    speaker_label: str,
    status_callback=None,
) -> str:
    validate_audio_file(
        audio_path
    )

    if status_callback:
        status_callback(
            f"Transcribing {speaker_label.lower()}..."
        )

    print(
        f"Uploading {audio_path.name}..."
    )

    uploaded_audio = (
        client.files.upload(
            file=str(audio_path)
        )
    )

    prompt = f"""
Transcribe this call audio accurately.

Speaker role:
{speaker_label}

Rules:
- Return only the transcript.
- Do not summarize.
- Do not create notes.
- Do not invent missing words.
- Preserve names, dates, numbers and important details.
- Preserve natural conversational wording.
- Remove meaningless filler only when it adds no value.
- If something is genuinely impossible to hear, write [inaudible].
- Do not repeatedly label the speaker.
- Never change the speaker's role or identity.
"""

    response = generate_with_retry(
        contents=[
            prompt,
            uploaded_audio,
        ],
        status_callback=status_callback,
    )

    if not response.text:
        raise RuntimeError(
            f"No transcript was returned "
            f"for {speaker_label}."
        )

    return response.text.strip()


def create_combined_transcript(
    my_transcript: str,
    their_transcript: str,
    remote_participant_name: str | None = None,
) -> str:
    remote_label = (
        f"THEM / {remote_participant_name}"
        if remote_participant_name
        else "THEM / REMOTE SPEAKER"
    )

    return f"""
============================================================
ME / LOCAL SPEAKER
============================================================

{my_transcript}


============================================================
{remote_label}
============================================================

{their_transcript}
""".strip()


def create_structured_transcript(
    my_transcript: str,
    their_transcript: str,
    call_title: str | None = None,
    remote_participant_name: str | None = None,
) -> dict:
    participants = [
        {
            "role": "me",
            "name": None,
            "source": "local-speaker",
        },
        {
            "role": "them",
            "name": remote_participant_name,
            "source": (
                "call-title"
                if remote_participant_name
                else None
            ),
        },
    ]

    return {
        "call_title": call_title,
        "participants": participants,
        "turns": [
            {
                "speaker": "me",
                "text": my_transcript,
            },
            {
                "speaker": "them",
                "text": their_transcript,
            },
        ],
    }


def transcribe_call(
    call_directory: str | Path,
    call_title: str | None = None,
    status_callback=None,
) -> dict:
    call_directory = Path(
        call_directory
    )

    mic_audio = call_directory / "mic_raw.wav"
    system_audio = call_directory / "system_raw.wav"

    my_transcript_file = (
        call_directory / "my_transcript.txt"
    )
    their_transcript_file = (
        call_directory / "their_transcript.txt"
    )
    combined_file = (
        call_directory / "combined_transcript.txt"
    )
    structured_file = (
        call_directory / "transcript.json"
    )

    remote_participant_name = (
        infer_remote_participant_name(call_title)
    )

    their_label = (
        f"THEM / {remote_participant_name}"
        if remote_participant_name
        else "THEM / REMOTE SPEAKER"
    )

    # Mic and system recordings are independent. Run exactly two
    # transcription requests concurrently; never transcribe either
    # side a second time.
    if status_callback:
        status_callback(
            "Transcribing both sides of the call..."
        )

    with ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="tca-transcription",
    ) as executor:
        my_future = executor.submit(
            transcribe_audio,
            audio_path=mic_audio,
            speaker_label="ME / LOCAL SPEAKER",
            status_callback=status_callback,
        )
        their_future = executor.submit(
            transcribe_audio,
            audio_path=system_audio,
            speaker_label=their_label,
            status_callback=status_callback,
        )

        my_transcript = my_future.result()
        their_transcript = their_future.result()

    my_transcript_file.write_text(
        my_transcript,
        encoding="utf-8",
    )
    their_transcript_file.write_text(
        their_transcript,
        encoding="utf-8",
    )

    combined_transcript = create_combined_transcript(
        my_transcript,
        their_transcript,
        remote_participant_name,
    )
    combined_file.write_text(
        combined_transcript,
        encoding="utf-8",
    )

    structured_transcript = create_structured_transcript(
        my_transcript=my_transcript,
        their_transcript=their_transcript,
        call_title=call_title,
        remote_participant_name=remote_participant_name,
    )
    structured_file.write_text(
        json.dumps(
            structured_transcript,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Saved transcript to: {combined_file}")
    print(f"Saved structured transcript to: {structured_file}")

    return {
        "my_transcript": my_transcript,
        "their_transcript": their_transcript,
        "combined_transcript": combined_transcript,
        "structured_transcript": structured_transcript,
        "remote_participant_name": remote_participant_name,
        "my_transcript_file": str(my_transcript_file),
        "their_transcript_file": str(their_transcript_file),
        "combined_transcript_file": str(combined_file),
        "structured_transcript_file": str(structured_file),
    }


if __name__ == "__main__":
    raise SystemExit(
        "V0.4 transcription is call-specific. "
        "Run it through the TCA backend."
    )
