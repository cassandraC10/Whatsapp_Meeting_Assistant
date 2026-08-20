import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY was not found.\n"
        "Add it to your .env file like:\n"
        "GEMINI_API_KEY=your_key_here"
    )

client = genai.Client(api_key=API_KEY)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MIC_AUDIO_FILE = PROJECT_ROOT / "mic_raw.wav"
SYSTEM_AUDIO_FILE = PROJECT_ROOT / "system_raw.wav"

MY_TRANSCRIPT_FILE = PROJECT_ROOT / "my_transcript.txt"
CLIENT_TRANSCRIPT_FILE = PROJECT_ROOT / "client_transcript.txt"

COMBINED_TRANSCRIPT_FILE = PROJECT_ROOT / "combined_transcript.txt"


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
# AUDIO VALIDATION
# ============================================================


def validate_audio_file(audio_path):

    if not audio_path.exists():

        raise FileNotFoundError(f"Audio file does not exist:\n" f"{audio_path}")

    if audio_path.stat().st_size == 0:

        raise RuntimeError(f"Audio file is empty:\n" f"{audio_path}")


# ============================================================
# UPLOAD AUDIO
# ============================================================


def upload_audio(audio_path):

    print(f"Uploading {audio_path.name}...")

    uploaded_file = client.files.upload(file=str(audio_path))

    print(f"Uploaded {audio_path.name}")

    return uploaded_file


# ============================================================
# TEMPORARY GEMINI ERROR DETECTION
# ============================================================


def is_temporary_gemini_error(error):
    """
    Returns True for errors that are worth retrying.
    """

    message = str(error).lower()

    temporary_markers = [
        "503",
        "unavailable",
        "high demand",
        "resource exhausted",
        "429",
        "temporarily",
        "timeout",
        "deadline exceeded",
    ]

    return any(marker in message for marker in temporary_markers)


# ============================================================
# GENERATE WITH RETRY
# ============================================================


def generate_with_retry(
    model,
    contents,
    status_callback=None,
):
    """
    Calls Gemini and retries temporary failures.

    status_callback is optional and can later
    be connected to the GUI.
    """

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(f"Gemini attempt " f"{attempt}/{MAX_RETRIES}...")

            response = client.models.generate_content(
                model=model,
                contents=contents,
            )

            return response

        except Exception as error:

            last_error = error

            temporary = is_temporary_gemini_error(error)

            if not temporary:
                raise

            if attempt >= MAX_RETRIES:
                break

            delay = RETRY_DELAYS[attempt - 1]

            message = (
                f"Gemini is temporarily busy. "
                f"Retrying in {delay} seconds "
                f"({attempt}/{MAX_RETRIES})..."
            )

            print(message)

            if status_callback:
                status_callback(message)

            time.sleep(delay)

    raise RuntimeError(
        "Gemini could not complete the request "
        "after multiple retries.\n"
        f"Last error: {last_error}"
    )


# ============================================================
# TRANSCRIBE AUDIO
# ============================================================


def transcribe_audio(
    audio_path,
    speaker_label,
    status_callback=None,
):

    validate_audio_file(audio_path)

    uploaded_audio = upload_audio(audio_path)

    print(f"Transcribing {speaker_label}...")

    prompt = f"""
You are transcribing one speaker's audio from a business meeting.

Speaker identity:
{speaker_label}

Your task is to transcribe everything the speaker says as accurately as possible.

Rules:
- Return ONLY the transcript.
- Do not summarize.
- Do not create meeting notes.
- Do not add action items.
- Do not explain the audio.
- Do not add commentary.
- Do not invent words that were not spoken.
- Preserve names, dates, numbers, deadlines, amounts, and business terminology carefully.
- Preserve the meaning of Nigerian English, accents, and conversational expressions.
- Remove obvious filler sounds only when they add no meaning.
- If a short section is genuinely impossible to understand, write [inaudible].
- Do not label the speaker on every line.
- Keep natural paragraph breaks.
"""

    response = generate_with_retry(
        model=MODEL_NAME,
        contents=[
            prompt,
            uploaded_audio,
        ],
        status_callback=status_callback,
    )

    if not response.text:

        raise RuntimeError(f"Gemini returned no transcript " f"for {speaker_label}.")

    transcript = response.text.strip()

    print(f"{speaker_label} transcription complete.")

    return transcript


# ============================================================
# SAVE TEXT FILE
# ============================================================


def save_transcript(
    transcript,
    output_path,
):

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(transcript)

    print(f"Saved {output_path.name}")


# ============================================================
# CREATE COMBINED TRANSCRIPT
# ============================================================


def create_combined_transcript(
    my_transcript,
    client_transcript,
):

    combined = f"""
============================================================
ME / LOCAL SPEAKER
============================================================

{my_transcript}


============================================================
CLIENT / REMOTE SPEAKER
============================================================

{client_transcript}
""".strip()

    return combined


# ============================================================
# TRANSCRIBE COMPLETE MEETING
# ============================================================


def transcribe_meeting(
    status_callback=None,
):

    print()
    print("========================================")
    print("      Gemini Meeting Transcriber")
    print("========================================")

    print()

    print(f"Model: {MODEL_NAME}")

    # --------------------------------------------------------
    # LOCAL / ME
    # --------------------------------------------------------

    print()
    print("STEP 1/3 — Transcribing local speaker")

    if status_callback:

        status_callback("Transcribing local speaker...")

    my_transcript = transcribe_audio(
        MIC_AUDIO_FILE,
        "ME / LOCAL SPEAKER",
        status_callback=status_callback,
    )

    save_transcript(
        my_transcript,
        MY_TRANSCRIPT_FILE,
    )

    # --------------------------------------------------------
    # REMOTE / CLIENT
    # --------------------------------------------------------

    print()

    print("STEP 2/3 — Transcribing remote speaker")

    if status_callback:

        status_callback("Transcribing remote speaker...")

    client_transcript = transcribe_audio(
        SYSTEM_AUDIO_FILE,
        "CLIENT / REMOTE SPEAKER",
        status_callback=status_callback,
    )

    save_transcript(
        client_transcript,
        CLIENT_TRANSCRIPT_FILE,
    )

    # --------------------------------------------------------
    # COMBINED
    # --------------------------------------------------------

    print()

    print("STEP 3/3 — Creating combined transcript")

    combined_transcript = create_combined_transcript(
        my_transcript,
        client_transcript,
    )

    save_transcript(
        combined_transcript,
        COMBINED_TRANSCRIPT_FILE,
    )

    print()

    print("========================================")
    print("              SUCCESS")
    print("========================================")

    return {
        "my_transcript": my_transcript,
        "client_transcript": client_transcript,
        "combined_transcript": combined_transcript,
    }


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    transcribe_meeting()
