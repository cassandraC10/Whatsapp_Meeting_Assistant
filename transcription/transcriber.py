import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

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


def is_daily_quota_error(error) -> bool:
    message = str(error).lower()

    markers = [
        "requestsperday",
        "perdayperproject",
        "generate requests per day",
    ]

    return any(
        marker in message
        for marker in markers
    )


def is_temporary_gemini_error(error) -> bool:
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

            if is_daily_quota_error(error):
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

Speaker:
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
) -> str:
    return f"""
============================================================
ME / LOCAL SPEAKER
============================================================

{my_transcript}


============================================================
THEM / REMOTE SPEAKER
============================================================

{their_transcript}
""".strip()


def transcribe_call(
    call_directory: str | Path,
    status_callback=None,
) -> dict:
    call_directory = Path(
        call_directory
    )

    mic_audio = (
        call_directory
        / "mic_raw.wav"
    )

    system_audio = (
        call_directory
        / "system_raw.wav"
    )

    my_transcript_file = (
        call_directory
        / "my_transcript.txt"
    )

    their_transcript_file = (
        call_directory
        / "their_transcript.txt"
    )

    combined_file = (
        call_directory
        / "combined_transcript.txt"
    )

    if status_callback:
        status_callback(
            "Transcribing your side of the call..."
        )

    my_transcript = transcribe_audio(
        audio_path=mic_audio,
        speaker_label="ME / LOCAL SPEAKER",
        status_callback=status_callback,
    )

    my_transcript_file.write_text(
        my_transcript,
        encoding="utf-8",
    )

    if status_callback:
        status_callback(
            "Transcribing the other side..."
        )

    their_transcript = transcribe_audio(
        audio_path=system_audio,
        speaker_label="THEM / REMOTE SPEAKER",
        status_callback=status_callback,
    )

    their_transcript_file.write_text(
        their_transcript,
        encoding="utf-8",
    )

    combined_transcript = (
        create_combined_transcript(
            my_transcript,
            their_transcript,
        )
    )

    combined_file.write_text(
        combined_transcript,
        encoding="utf-8",
    )

    print(
        f"Saved transcript to: "
        f"{combined_file}"
    )

    return {
        "my_transcript": my_transcript,
        "their_transcript": their_transcript,
        "combined_transcript": (
            combined_transcript
        ),
        "my_transcript_file": str(
            my_transcript_file
        ),
        "their_transcript_file": str(
            their_transcript_file
        ),
        "combined_transcript_file": str(
            combined_file
        ),
    }


if __name__ == "__main__":
    raise SystemExit(
        "V2 transcription is call-specific. "
        "Run it through the TCA backend."
    )