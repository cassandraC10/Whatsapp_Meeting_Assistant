from backend.app.models import (
    Call,
    CallStatus,
)
from backend.app.repository import (
    CallRepository,
)
from intelligence.summarizer import (
    summarize_call,
)
from transcription.transcriber import (
    infer_remote_participant_name,
    transcribe_call,
)


class CallProcessingService:
    def __init__(
        self,
        repository: CallRepository,
    ):
        self.repository = repository

    def process(
        self,
        call: Call,
        status_callback=None,
    ) -> dict:
        call_directory = (
            self.repository.get_directory(
                call.id
            )
        )

        mic_file = (
            call_directory
            / "mic_raw.wav"
        )

        system_file = (
            call_directory
            / "system_raw.wav"
        )

        if not mic_file.exists():
            raise RuntimeError(
                "Microphone recording is missing."
            )

        if not system_file.exists():
            raise RuntimeError(
                "System recording is missing."
            )

        call.status = (
            CallStatus.PROCESSING
        )

        self.repository.save(
            call
        )

        try:
            if status_callback:
                status_callback(
                    "Transcribing the conversation..."
                )

            remote_participant_name = (
                infer_remote_participant_name(
                    call.title
                )
            )

            transcript_result = (
                transcribe_call(
                    call_directory=(
                        call_directory
                    ),
                    call_title=call.title,
                    status_callback=(
                        status_callback
                    ),
                )
            )

            combined_transcript = (
                transcript_result[
                    "combined_transcript"
                ]
            )

            if not combined_transcript.strip():
                raise RuntimeError(
                    "Transcription returned "
                    "an empty transcript."
                )

            if status_callback:
                status_callback(
                    "Preparing your notes..."
                )

            notes, text_notes = (
                summarize_call(
                    call_directory=(
                        call_directory
                    ),
                    call_title=call.title,
                    remote_participant_name=(
                        remote_participant_name
                    ),
                    status_callback=(
                        status_callback
                    ),
                )
            )

            call.status = (
                CallStatus.COMPLETED
            )

            self.repository.save(
                call
            )

            return {
                "call": call,
                "transcript": (
                    combined_transcript
                ),
                "notes": (
                    notes.model_dump()
                ),
                "text_notes": (
                    text_notes
                ),
            }

        except Exception:
            call.status = (
                CallStatus.FAILED
            )

            self.repository.save(
                call
            )

            raise
