import os
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


client = genai.Client(
    api_key=API_KEY
)


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

# Use a Flash model for the MVP because transcription
# does not require the most expensive reasoning model.
#
# If your AI Studio account shows a different current
# free-tier Flash model, you can change only this value.
MODEL_NAME = "gemini-3.5-flash"


# ============================================================
# AUDIO VALIDATION
# ============================================================

def validate_audio_file(audio_path):
    """
    Makes sure the recording exists and is not empty.
    """

    if not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file does not exist:\n{audio_path}"
        )

    if audio_path.stat().st_size == 0:
        raise RuntimeError(
            f"Audio file is empty:\n{audio_path}"
        )


# ============================================================
# UPLOAD AUDIO
# ============================================================

def upload_audio(audio_path):
    """
    Uploads a WAV recording to Gemini's Files API.
    """

    print(
        f"Uploading {audio_path.name}..."
    )

    uploaded_file = client.files.upload(
        file=str(audio_path)
    )

    print(
        f"Uploaded {audio_path.name}"
    )

    return uploaded_file


# ============================================================
# TRANSCRIBE AUDIO
# ============================================================

def transcribe_audio(
    audio_path,
    speaker_label,
):
    """
    Uploads an audio file and asks Gemini to
    return a clean verbatim transcript.
    """

    validate_audio_file(
        audio_path
    )

    uploaded_audio = upload_audio(
        audio_path
    )

    print(
        f"Transcribing {speaker_label}..."
    )

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

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            prompt,
            uploaded_audio,
        ],
    )

    if not response.text:
        raise RuntimeError(
            f"Gemini returned no transcript "
            f"for {speaker_label}."
        )

    transcript = response.text.strip()

    print(
        f"{speaker_label} transcription complete."
    )

    return transcript


# ============================================================
# SAVE TEXT FILE
# ============================================================

def save_transcript(
    transcript,
    output_path,
):
    """
    Saves transcript as UTF-8 text.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            transcript
        )

    print(
        f"Saved {output_path.name}"
    )


# ============================================================
# CREATE COMBINED SPEAKER FILE
# ============================================================

def create_combined_transcript(
    my_transcript,
    client_transcript,
):
    """
    Creates a speaker-aware text file that
    we can feed into the meeting-note AI stage.

    NOTE:
    The two recordings are transcribed independently,
    so this does not yet reconstruct perfect conversational
    turn order.
    """

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

def transcribe_meeting():
    """
    Transcribes the local microphone and
    remote/system recording separately.
    """

    print()
    print(
        "========================================"
    )
    print(
        "      Gemini Meeting Transcriber"
    )
    print(
        "========================================"
    )

    print()

    print(
        f"Model: {MODEL_NAME}"
    )

    print()

    # ========================================================
    # LOCAL / ME
    # ========================================================

    print(
        "STEP 1/3 — Transcribing local speaker"
    )

    my_transcript = transcribe_audio(
        MIC_AUDIO_FILE,
        "ME / LOCAL SPEAKER",
    )

    save_transcript(
        my_transcript,
        MY_TRANSCRIPT_FILE,
    )

    # ========================================================
    # REMOTE / CLIENT
    # ========================================================

    print()

    print(
        "STEP 2/3 — Transcribing remote speaker"
    )

    client_transcript = transcribe_audio(
        SYSTEM_AUDIO_FILE,
        "CLIENT / REMOTE SPEAKER",
    )

    save_transcript(
        client_transcript,
        CLIENT_TRANSCRIPT_FILE,
    )

    # ========================================================
    # COMBINED SPEAKER-AWARE TRANSCRIPT
    # ========================================================

    print()

    print(
        "STEP 3/3 — Creating combined transcript"
    )

    combined_transcript = (
        create_combined_transcript(
            my_transcript,
            client_transcript,
        )
    )

    save_transcript(
        combined_transcript,
        COMBINED_TRANSCRIPT_FILE,
    )

    # ========================================================
    # COMPLETE
    # ========================================================

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
        "ME transcript:"
    )

    print(
        f"  {MY_TRANSCRIPT_FILE.name}"
    )

    print()

    print(
        "CLIENT transcript:"
    )

    print(
        f"  {CLIENT_TRANSCRIPT_FILE.name}"
    )

    print()

    print(
        "Combined speaker transcript:"
    )

    print(
        f"  {COMBINED_TRANSCRIPT_FILE.name}"
    )

    print()

    print(
        "Preview:"
    )

    print(
        "----------------------------------------"
    )

    print()

    print(
        "ME:"
    )

    print(
        my_transcript[:500]
    )

    print()

    print(
        "CLIENT:"
    )

    print(
        client_transcript[:500]
    )

    print()

    print(
        "----------------------------------------"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    transcribe_meeting()