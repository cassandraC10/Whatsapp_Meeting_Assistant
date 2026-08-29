import json

from fastapi import (
    FastAPI,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import (
    Call,
    CallStatus,
    CreateCallRequest,
)
from backend.app.processing_service import (
    CallProcessingService,
)
from backend.app.recorder_manager import (
    RecorderManager,
)
from backend.app.repository import (
    CallRepository,
)


app = FastAPI(
    title="TCA API",
    description=(
        "Backend API for "
        "TCA — The Call Assistant"
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


call_repository = CallRepository()

recorder_manager = RecorderManager()

processing_service = CallProcessingService(
    repository=call_repository
)


def recover_stale_call(
    call: Call,
) -> Call:
    """
    A recording only exists while its MeetingRecorder
    is alive in this Python process.

    If metadata says recording/paused but there is no
    live recorder, the previous session was interrupted.
    """

    if call.status not in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        return call

    if recorder_manager.is_recording(
        call.id
    ):
        return call

    call.status = CallStatus.FAILED
    call.failure_reason = (
        "recording_interrupted"
    )

    call_repository.save(call)

    return call


def recover_stale_calls() -> None:
    for call in call_repository.list_all():
        recover_stale_call(call)


# Clean up zombie recording states whenever
# this backend process starts.
recover_stale_calls()


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "TCA API",
        "version": "0.2.0",
    }


@app.post(
    "/calls",
    response_model=Call,
    status_code=status.HTTP_201_CREATED,
)
def create_call(
    request: CreateCallRequest,
):
    return call_repository.create(
        title=request.title
    )


@app.get(
    "/calls",
    response_model=list[Call],
)
def list_calls():
    calls = call_repository.list_all()

    return [
        recover_stale_call(call)
        for call in calls
    ]


@app.get(
    "/calls/{call_id}",
    response_model=Call,
)
def get_call(
    call_id: str,
):
    return require_call(call_id)


@app.post(
    "/calls/{call_id}/start",
    response_model=Call,
)
def start_call_recording(
    call_id: str,
):
    call = require_call(call_id)

    if call.status in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call already has "
                "an active recording."
            ),
        )

    if call.status == CallStatus.PROCESSING:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call is already processing."
            ),
        )

    if call.status == CallStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call is already completed. "
                "Create a new call instead."
            ),
        )

    call_directory = (
        call_repository.get_directory(
            call_id
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

    # A failed processing job may still have a
    # perfectly good recording. Do not overwrite it.
    if (
        call.status == CallStatus.FAILED
        and mic_file.exists()
        and system_file.exists()
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This call already has a saved "
                "recording. Try processing it again "
                "instead of recording over it."
            ),
        )

    if recorder_manager.is_recording(
        call_id
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "An active recorder already "
                "exists for this call."
            ),
        )

    try:
        recorder_manager.start(
            call_id=call_id,
            output_directory=call_directory,
        )

    except Exception as error:
        call.status = CallStatus.FAILED
        call.failure_reason = (
            "recording_start_failed"
        )

        call_repository.save(call)

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not start recording: "
                f"{error}"
            ),
        ) from error

    call.status = CallStatus.RECORDING
    call.failure_reason = None

    call_repository.save(call)

    return call


@app.post(
    "/calls/{call_id}/pause",
    response_model=Call,
)
def pause_call_recording(
    call_id: str,
):
    call = require_call(call_id)

    if call.status != CallStatus.RECORDING:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an active recording "
                "can be paused."
            ),
        )

    if not recorder_manager.is_recording(
        call_id
    ):
        call.status = CallStatus.FAILED
        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(call)

        raise HTTPException(
            status_code=409,
            detail=(
                "This recording session "
                "was interrupted."
            ),
        )

    try:
        recorder_manager.pause(
            call_id
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not pause recording: "
                f"{error}"
            ),
        ) from error

    call.status = CallStatus.PAUSED

    call_repository.save(call)

    return call


@app.post(
    "/calls/{call_id}/resume",
    response_model=Call,
)
def resume_call_recording(
    call_id: str,
):
    call = require_call(call_id)

    if call.status != CallStatus.PAUSED:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only a paused recording "
                "can be resumed."
            ),
        )

    if not recorder_manager.is_recording(
        call_id
    ):
        call.status = CallStatus.FAILED
        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(call)

        raise HTTPException(
            status_code=409,
            detail=(
                "This recording session "
                "was interrupted."
            ),
        )

    try:
        recorder_manager.resume(
            call_id
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not resume recording: "
                f"{error}"
            ),
        ) from error

    call.status = CallStatus.RECORDING

    call_repository.save(call)

    return call


@app.post(
    "/calls/{call_id}/finish",
)
def finish_call_recording(
    call_id: str,
):
    call = require_call(call_id)

    if call.status not in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call does not have "
                "an active recording."
            ),
        )

    if not recorder_manager.is_recording(
        call_id
    ):
        call.status = CallStatus.FAILED
        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(call)

        raise HTTPException(
            status_code=409,
            detail=(
                "The recording session ended "
                "unexpectedly before it could "
                "be finished."
            ),
        )

    try:
        recording_result = (
            recorder_manager.finish(
                call_id
            )
        )

    except Exception as error:
        call.status = CallStatus.FAILED
        call.failure_reason = (
            "recording_finish_failed"
        )

        call_repository.save(call)

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not finish recording: "
                f"{error}"
            ),
        ) from error

    call.duration_seconds = (
        recording_result[
            "duration"
        ]
    )

    call.status = (
        CallStatus.PROCESSING
    )

    call.failure_reason = None

    call_repository.save(call)

    return {
        "call": call,
        "recording": {
            "mic": (
                recording_result[
                    "mic"
                ]
            ),
            "system": (
                recording_result[
                    "system"
                ]
            ),
            "mixed": (
                recording_result[
                    "mixed"
                ]
            ),
            "duration_seconds": (
                recording_result[
                    "duration"
                ]
            ),
        },
    }


@app.get(
    "/calls/{call_id}/recording-status",
)
def get_recording_status(
    call_id: str,
):
    call = require_call(call_id)

    return {
        "call_id": call.id,
        "status": call.status,
        "is_recording": (
            recorder_manager.is_recording(
                call_id
            )
        ),
        "is_paused": (
            recorder_manager.is_paused(
                call_id
            )
        ),
        "elapsed_seconds": (
            recorder_manager.elapsed_seconds(
                call_id
            )
        ),
        "failure_reason": (
            call.failure_reason
        ),
    }


@app.post(
    "/calls/{call_id}/process",
)
def process_call(
    call_id: str,
):
    call = require_call(call_id)

    call_directory = (
        call_repository.get_directory(
            call_id
        )
    )

    if call.status in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Finish the recording before "
                "processing the call."
            ),
        )

    mic_file = (
        call_directory
        / "mic_raw.wav"
    )

    system_file = (
        call_directory
        / "system_raw.wav"
    )

    if (
        not mic_file.exists()
        or not system_file.exists()
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This call does not have "
                "a complete saved recording."
            ),
        )

    call.status = CallStatus.PROCESSING
    call.failure_reason = None

    call_repository.save(call)

    try:
        return processing_service.process(
            call
        )

    except Exception as error:
        latest_call = (
            call_repository.get(
                call_id
            )
            or call
        )

        latest_call.status = (
            CallStatus.FAILED
        )

        latest_call.failure_reason = (
            "processing_failed"
        )

        call_repository.save(
            latest_call
        )

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@app.get(
    "/calls/{call_id}/transcript",
)
def get_call_transcript(
    call_id: str,
):
    require_call(call_id)

    call_directory = (
        call_repository.get_directory(
            call_id
        )
    )

    transcript_file = (
        call_directory
        / "combined_transcript.txt"
    )

    if not transcript_file.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Transcript not available."
            ),
        )

    return {
        "call_id": call_id,
        "transcript": (
            transcript_file.read_text(
                encoding="utf-8"
            )
        ),
    }


@app.get(
    "/calls/{call_id}/notes",
)
def get_call_notes(
    call_id: str,
):
    call = require_call(call_id)

    call_directory = (
        call_repository.get_directory(
            call_id
        )
    )

    notes_file = (
        call_directory
        / "notes.json"
    )

    if not notes_file.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "Notes not available."
            ),
        )

    notes = json.loads(
        notes_file.read_text(
            encoding="utf-8"
        )
    )

    return {
        "call": call,
        "notes": notes,
    }


def require_call(
    call_id: str,
) -> Call:
    call = call_repository.get(
        call_id
    )

    if call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found.",
        )

    return recover_stale_call(
        call
    )