import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY was not found. "
        "Add it to your .env file."
    )

client = OpenAI(
    api_key=API_KEY
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MIC_AUDIO_FILE = PROJECT_ROOT / "mic_raw.wav"
SYSTEM_AUDIO_FILE = PROJECT_ROOT / "system_raw.wav"

MY_TRANSCRIPT_FILE = PROJECT_ROOT / "my_transcript.txt"
CLIENT_TRANSCRIPT_FILE = PROJECT_ROOT / "client_transcript.txt"


# ============================================================
# TRANSCRIPTION
# ============================================================

def transcribe_audio(audio_path):
    """
    Sends an audio file to the transcription API
    and returns the text transcript.
    """

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    print(
        f"Transcribing: {audio_path.name}"
    )

    with open(audio_path, "rb") as audio_file:

        transcription = (
            client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio_file,
            )
        )

    return transcription.text.strip()


# ============================================================
# SAVE
# ============================================================

def save_transcript(
    transcript,
    output_path,
):
    """
    Saves transcript text to disk.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(transcript)

    print(
        f"Saved: {output_path.name}"
    )


# ============================================================
# SPEAKER-AWARE TRANSCRIPTION
# ============================================================

def transcribe_meeting():
    """
    Transcribes local and remote audio separately.
    """

    print()
    print(
        "========================================"
    )
    print(
        "      Meeting Transcription"
    )
    print(
        "========================================"
    )
    print()

    # --------------------------------------------------------
    # ME / LOCAL MICROPHONE
    # --------------------------------------------------------

    print("Transcribing local speaker...")

    my_transcript = transcribe_audio(
        MIC_AUDIO_FILE
    )

    save_transcript(
        my_transcript,
        MY_TRANSCRIPT_FILE,
    )

    print()
    print("ME:")
    print(my_transcript)

    # --------------------------------------------------------
    # CLIENT / REMOTE
    # --------------------------------------------------------

    print()
    print("Transcribing remote speaker...")

    client_transcript = transcribe_audio(
        SYSTEM_AUDIO_FILE
    )

    save_transcript(
        client_transcript,
        CLIENT_TRANSCRIPT_FILE,
    )

    print()
    print("CLIENT:")
    print(client_transcript)

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print(
        "========================================"
    )
    print(
        "              SUCCESS"
    )
    print(
        "========================================"
    )

    print()

    print(
        f"ME transcript: "
        f"{MY_TRANSCRIPT_FILE.name}"
    )

    print(
        f"CLIENT transcript: "
        f"{CLIENT_TRANSCRIPT_FILE.name}"
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    transcribe_meeting()