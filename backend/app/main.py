import json

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from backend.app.ask_service import AskTCAService
from backend.app.config import get_config, is_analytics_admin, validate_startup
from backend.app.auth import (
    authenticate_user,
    create_access_token,
    create_capture_handoff,
    create_user,
    exchange_capture_handoff,
    get_current_user,
    initialize_auth_database,
    update_user_profile,
)
from backend.app.cloud import (
    cloud_health,
    initialize_cloud_foundation,
    sync_cloud_user,
)
from backend.app.event_store import initialize_event_store, record_product_event
from backend.app.analytics import build_analytics_snapshot, initialize_analytics_store, reset_ai_context, set_ai_context
from backend.app.feedback import (
    get_feedback,
    initialize_feedback_store,
    submit_feedback,
)
from backend.app.models import (
    AskTCARequest,
    AskTCAResponse,
    Call,
    CallStatus,
    CreateCallRequest,
    UpdateCallRequest,
    AuthResponse,
    AuthUserResponse,
    CaptureHandoffExchangeRequest,
    CaptureHandoffResponse,
    FeedbackResponse,
    LoginRequest,
    SubmitFeedbackRequest,
    SignupRequest,
    UpdateProfileRequest,
    AnalyticsResponse,
    PersonDetail,
    PeopleResponse,
    Task,
    TasksResponse,
    UpdateTaskRequest,
)
from backend.app.processing_service import CallProcessingService
from backend.app.recorder_manager import RecorderManager
from backend.app.repository import CallRepository
from intelligence.summarizer import generate_follow_up

app = FastAPI(
    title="TCA API",
    description=(
        "Backend API for "
        "TCA — The Call Assistant"
    ),
    version="0.5.0",
)


config = validate_startup()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

allowed_hosts = [
    item.strip()
    for item in __import__("os").getenv("TCA_ALLOWED_HOSTS", "*").split(",")
    if item.strip()
]
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts or ["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if config.production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response



call_repository = (
    CallRepository()
)

recorder_manager = (
    RecorderManager()
)

processing_service = (
    CallProcessingService(
        repository=call_repository
    )
)

ask_service = (
    AskTCAService(
        repository=call_repository
    )
)


AUDIO_UPLOAD_CONTENT_TYPES = {
    "audio/webm",
    "video/webm",
    "audio/ogg",
    "application/ogg",
    "audio/mp4",
    "audio/mpeg",
}
AUDIO_UPLOAD_EXTENSIONS = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
}


def _validate_audio_upload(upload: UploadFile, field_name: str) -> str:
    # Browser MediaRecorder commonly reports codec parameters, e.g.
    # ``audio/webm;codecs=opus``. FastAPI exposes that exact value as
    # UploadFile.content_type, so exact matching would reject perfectly valid
    # browser recordings with HTTP 415. Normalize parameters before validating.
    raw_content_type = (upload.content_type or "").strip().casefold()
    content_type = raw_content_type.split(";", 1)[0].strip()
    if content_type not in AUDIO_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"{field_name} must be WebM/Opus or Ogg/Opus audio. "
                f"Received {raw_content_type or 'unknown content type'}."
            ),
        )
    return AUDIO_UPLOAD_EXTENSIONS[content_type]


async def _save_audio_upload(
    upload: UploadFile,
    destination,
    max_bytes: int,
) -> int:
    total = 0
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio upload is larger than the configured capture limit.",
                    )
                handle.write(chunk)
    finally:
        await upload.close()

    if total == 0:
        raise HTTPException(
            status_code=400,
            detail="Audio upload is empty.",
        )

    return total


def recover_stale_call(
    call: Call,
) -> Call:
    if config.capture_mode == "browser":
        return call

    if call.status not in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        return call

    if (
        recorder_manager
        .is_recording(
            call.id
        )
    ):
        return call

    call.status = (
        CallStatus.FAILED
    )

    call.failure_reason = (
        "recording_interrupted"
    )

    call_repository.save(
        call
    )

    return call


def recover_stale_calls() -> None:
    for call in (
        call_repository.list_all()
    ):
        recover_stale_call(
            call
        )


cloud_startup_status = initialize_cloud_foundation()
initialize_auth_database()
initialize_event_store()
initialize_feedback_store()
initialize_analytics_store()
recover_stale_calls()


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "TCA API",
        "version": "0.5.0",
        "environment": config.environment,
        "cloud": cloud_startup_status,
        "capture_mode": config.capture_mode,
    }


@app.get("/health/ready")
def readiness_check():
    cloud_status = cloud_health()
    checks = {
        "config": "ok",
        "cloud_database": "ok" if (not config.cloud_required or cloud_status.get("database", {}).get("status") == "ok") else "error",
        "gemini": "ok" if config.gemini_api_key else "missing",
    }
    ready = all(value == "ok" for value in checks.values())
    payload = {
        "status": "ready" if ready else "not_ready",
        "environment": config.environment,
        "checks": checks,
        "capture": {
            "mode": config.capture_mode,
            "server_audio_available": config.capture_mode == "local_server",
            "note": (
                "Local Windows audio capture is available only where the local audio devices exist."
                if config.capture_mode == "local_server"
                else "Browser capture endpoint is configured; use the browser capture client."
            ),
        },
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


@app.get("/health/cloud")
def cloud_health_check():
    return cloud_health()


@app.post(
    "/auth/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def signup(request: SignupRequest):
    try:
        user = create_user(
            name=request.name,
            email=request.email,
            password=request.password,
        )
    except ValueError as error:
        message = str(error)
        status_code = 409 if "already exists" in message.lower() else 400
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error

    call_repository.claim_legacy_calls(user.id)
    record_product_event(
        user_id=user.id,
        event_name="sign_up",
        properties={"source": "email"},
    )
    try:
        sync_cloud_user(user)
    except Exception:
        # Cloud Foundation is a preparation layer. Local auth remains
        # authoritative until the cloud-memory/auth migration is enabled.
        pass

    return AuthResponse(
        access_token=create_access_token(user),
        user=AuthUserResponse(**user.to_public_dict()),
    )


@app.post(
    "/auth/login",
    response_model=AuthResponse,
)
def login(request: LoginRequest):
    user = authenticate_user(
        email=request.email,
        password=request.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    call_repository.claim_legacy_calls(user.id)
    record_product_event(
        user_id=user.id,
        event_name="login",
        properties={"source": "email"},
    )
    try:
        sync_cloud_user(user)
    except Exception:
        pass

    return AuthResponse(
        access_token=create_access_token(user),
        user=AuthUserResponse(**user.to_public_dict()),
    )


@app.get(
    "/auth/me",
    response_model=AuthUserResponse,
)
def current_user(user=Depends(get_current_user)):
    return AuthUserResponse(**user.to_public_dict())


@app.post(
    "/auth/capture-handoff",
    response_model=CaptureHandoffResponse,
)
def create_native_capture_handoff(user=Depends(get_current_user)):
    code, expires_at = create_capture_handoff(user)
    record_product_event(
        user_id=user.id,
        event_name="capture_opened",
        properties={"source": "web_capture_button"},
    )
    return CaptureHandoffResponse(
        code=code,
        expires_at=expires_at,
    )


@app.post(
    "/auth/capture-handoff/exchange",
    response_model=AuthResponse,
)
def exchange_native_capture_handoff(
    request: CaptureHandoffExchangeRequest,
):
    user = exchange_capture_handoff(request.code)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This capture connection has expired or was already used.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthResponse(
        access_token=create_access_token(user),
        user=AuthUserResponse(**user.to_public_dict()),
    )


@app.patch(
    "/auth/me",
    response_model=AuthUserResponse,
)
def update_current_user(
    request: UpdateProfileRequest,
    user=Depends(get_current_user),
):
    was_onboarded = user.onboarding_completed

    try:
        updated = update_user_profile(
            user_id=user.id,
            name=request.name,
            onboarding_completed=request.onboarding_completed,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if (
        request.onboarding_completed
        and not was_onboarded
    ):
        record_product_event(
            user_id=updated.id,
            event_name="onboarding_completed",
        )

    try:
        sync_cloud_user(updated)
    except Exception:
        pass

    return AuthUserResponse(**updated.to_public_dict())


@app.post(
    "/calls",
    response_model=Call,
    status_code=(
        status.HTTP_201_CREATED
    ),
)
def create_call(
    request: CreateCallRequest,
    user=Depends(get_current_user),
):
    call = call_repository.create(
        title=request.title,
        user_id=user.id,
    )
    record_product_event(
        user_id=user.id,
        event_name="conversation_created",
        call_id=call.id,
        properties={"status": call.status.value},
    )
    return call


@app.get(
    "/calls",
    response_model=list[Call],
)
def list_calls(
    user=Depends(get_current_user),
):
    calls = (
        call_repository.list_all(
            user_id=user.id
        )
    )

    return [
        recover_stale_call(
            call
        )
        for call in calls
    ]


@app.get(
    "/calls/search",
)
def search_calls(
    q: str = Query(
        default="",
        max_length=200,
    ),
    user=Depends(get_current_user),
):
    query = (
        q.strip()
    )

    if not query:
        return {
            "query": "",
            "count": 0,
            "results": [],
        }

    results = (
        call_repository.search(
            query,
            user_id=user.id,
        )
    )

    record_product_event(
        user_id=user.id,
        event_name="search_used",
        properties={"query_length": len(query), "result_count": len(results)},
    )

    return {
        "query": query,
        "count": len(
            results
        ),
        "results": results,
    }


@app.post(
    "/ask",
    response_model=AskTCAResponse,
)
def ask_tca(
    request: AskTCARequest,
    user=Depends(get_current_user),
):
    try:
        result = ask_service.ask(
            question=(
                request.question
            ),
            call_id=(
                request.call_id
            ),
            user_id=user.id,
        )
        record_product_event(
            user_id=user.id,
            event_name="ask_tca_used",
            call_id=request.call_id,
            properties={"question_length": len(request.question)},
        )
        return result

    except RuntimeError as error:
        message = str(
            error
        )

        if (
            message
            == "Call not found."
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from error

        if (
            "only available for completed"
            in message.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail=message,
            ) from error

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from error


@app.get(
    "/calls/{call_id}",
    response_model=Call,
)
def get_call(
    call_id: str,
    user=Depends(get_current_user),
):
    return require_call(
        call_id,
        user,
    )


@app.patch(
    "/calls/{call_id}",
    response_model=Call,
)
def update_call(
    call_id: str,
    request: UpdateCallRequest,
    user=Depends(get_current_user),
):
    require_call(
        call_id,
        user,
    )

    try:
        updated_call = (
            call_repository.update_title(
                call_id=call_id,
                title=request.title,
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if updated_call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found.",
        )

    return updated_call


@app.get(
    "/people",
    response_model=PeopleResponse,
)
def get_people(
    user=Depends(get_current_user),
):
    return PeopleResponse(
        people=call_repository.list_people(
            user_id=user.id
        )
    )


@app.get(
    "/people/{person_id}",
    response_model=PersonDetail,
)
def get_person(
    person_id: str,
    user=Depends(get_current_user),
):
    person = call_repository.get_person_detail(
        person_id,
        user_id=user.id,
    )
    if person is None:
        raise HTTPException(
            status_code=404,
            detail="Person not found.",
        )
    return person


@app.get(
    "/calls/{call_id}/tasks",
    response_model=TasksResponse,
)
def get_call_tasks(
    call_id: str,
    user=Depends(get_current_user),
):
    require_call(
        call_id,
        user,
    )

    tasks = call_repository.get_tasks(
        call_id
    )

    return TasksResponse(
        call_id=call_id,
        tasks=tasks,
    )


@app.patch(
    "/calls/{call_id}/tasks/{task_id}",
    response_model=Task,
)
def update_call_task(
    call_id: str,
    task_id: str,
    request: UpdateTaskRequest,
    user=Depends(get_current_user),
):
    require_call(
        call_id,
        user,
    )

    if (
        request.task is None
        and request.deadline is None
        and request.completed is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Provide at least one task "
                "field to update."
            ),
        )

    if request.task is not None:
        cleaned_task = request.task.strip()

        if not cleaned_task:
            raise HTTPException(
                status_code=400,
                detail="Task text cannot be empty.",
            )
    else:
        cleaned_task = None

    updated_task = call_repository.update_task(
        call_id,
        task_id,
        task_text=cleaned_task,
        deadline=request.deadline,
        deadline_provided=(
            "deadline"
            in request.model_fields_set
        ),
        completed=request.completed,
    )

    if updated_task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found.",
        )

    return updated_task


@app.delete(
    "/calls/{call_id}/tasks/{task_id}",
)
def delete_call_task(
    call_id: str,
    task_id: str,
    user=Depends(get_current_user),
):
    require_call(
        call_id,
        user,
    )

    deleted = call_repository.delete_task(
        call_id,
        task_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Task not found.",
        )

    return {
        "status": "deleted",
        "call_id": call_id,
        "task_id": task_id,
    }


@app.delete(
    "/calls/{call_id}",
    status_code=(
        status.HTTP_200_OK
    ),
)
def delete_call(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if (
        recorder_manager
        .is_recording(
            call_id
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Finish the active "
                "recording before deleting "
                "this call."
            ),
        )

    if call.status in {
        CallStatus.RECORDING,
        CallStatus.PAUSED,
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call is still active "
                "and cannot be deleted yet."
            ),
        )

    if (
        call.status
        == CallStatus.PROCESSING
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Wait for processing to "
                "finish before deleting "
                "this call."
            ),
        )

    deleted = call_repository.delete(
        call_id,
        user_id=user.id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Call not found.",
        )

    return {
        "status": "deleted",
        "call_id": call_id,
    }


@app.post(
    "/calls/{call_id}/start",
    response_model=Call,
)
def start_call_recording(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

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

    if (
        call.status
        == CallStatus.PROCESSING
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This call is already "
                "processing."
            ),
        )

    if (
        call.status
        == CallStatus.COMPLETED
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This call is already "
                "completed. Create a new "
                "call instead."
            ),
        )

    call_directory = (
        call_repository
        .get_directory(
            call_id
        )
    )

    mic_file = call_directory / "mic_raw.wav"
    system_file = call_directory / "system_raw.wav"
    has_saved_capture = (
        mic_file.exists()
        and system_file.exists()
    ) or (
        any(call_directory.glob("mic_raw.*"))
        and any(call_directory.glob("system_raw.*"))
    )

    if (
        call.status
        == CallStatus.FAILED
        and has_saved_capture
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This call already has a "
                "saved recording. Try "
                "processing it again instead "
                "of recording over it."
            ),
        )

    if (
        recorder_manager
        .is_recording(
            call_id
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "An active recorder already "
                "exists for this call."
            ),
        )

    if config.capture_mode == "browser":
        call.status = CallStatus.RECORDING
        call.failure_reason = None
        call_repository.save(call)
        record_product_event(
            user_id=user.id,
            event_name="recording_started",
            call_id=call.id,
            properties={"title": call.title, "capture_mode": "browser"},
        )
        return call

    if config.capture_mode != "local_server":
        raise HTTPException(
            status_code=409,
            detail=(
                "This deployment does not have a supported capture mode."
            ),
        )

    try:
        recorder_manager.start(
            call_id=call_id,
            output_directory=(
                call_directory
            ),
        )

    except Exception as error:
        call.status = (
            CallStatus.FAILED
        )

        call.failure_reason = (
            "recording_start_failed"
        )

        call_repository.save(
            call
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not start recording: "
                f"{error}"
            ),
        ) from error

    call.status = (
        CallStatus.RECORDING
    )

    call.failure_reason = None

    call_repository.save(
        call
    )
    record_product_event(
        user_id=user.id,
        event_name="recording_started",
        call_id=call.id,
        properties={"title": call.title},
    )

    return call


@app.post(
    "/calls/{call_id}/pause",
    response_model=Call,
)
def pause_call_recording(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if (
        call.status
        != CallStatus.RECORDING
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Only an active recording "
                "can be paused."
            ),
        )

    if config.capture_mode == "browser":
        call.status = CallStatus.PAUSED
        call_repository.save(call)
        return call

    if not (
        recorder_manager
        .is_recording(
            call_id
        )
    ):
        call.status = (
            CallStatus.FAILED
        )

        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(
            call
        )

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

    call.status = (
        CallStatus.PAUSED
    )

    call_repository.save(
        call
    )

    return call


@app.post(
    "/calls/{call_id}/resume",
    response_model=Call,
)
def resume_call_recording(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if (
        call.status
        != CallStatus.PAUSED
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Only a paused recording "
                "can be resumed."
            ),
        )

    if config.capture_mode == "browser":
        call.status = CallStatus.RECORDING
        call_repository.save(call)
        return call

    if not (
        recorder_manager
        .is_recording(
            call_id
        )
    ):
        call.status = (
            CallStatus.FAILED
        )

        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(
            call
        )

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

    call.status = (
        CallStatus.RECORDING
    )

    call_repository.save(
        call
    )

    return call


@app.post(
    "/calls/{call_id}/capture",
)
async def upload_browser_capture(
    call_id: str,
    request: Request,
    mic_audio: UploadFile = File(...),
    system_audio: UploadFile = File(...),
    duration_seconds: float = Form(...),
    user=Depends(get_current_user),
):
    call = require_call(call_id, user)

    if config.capture_mode != "browser":
        raise HTTPException(
            status_code=409,
            detail="Browser capture uploads are disabled for this deployment.",
        )

    if call.status not in {CallStatus.RECORDING, CallStatus.PAUSED}:
        raise HTTPException(
            status_code=409,
            detail="This call is not in an active recording state.",
        )

    if duration_seconds <= 0 or duration_seconds > 24 * 60 * 60:
        raise HTTPException(
            status_code=400,
            detail="Recording duration is invalid.",
        )

    max_bytes = config.max_body_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"The complete capture upload is larger than "
                        f"the configured {config.max_body_mb} MB limit."
                    ),
                )
        except ValueError:
            pass

    mic_extension = _validate_audio_upload(mic_audio, "Microphone audio")
    system_extension = _validate_audio_upload(system_audio, "System audio")

    call_directory = call_repository.get_directory(call_id)
    mic_destination = call_directory / f"mic_raw{mic_extension}"
    system_destination = call_directory / f"system_raw{system_extension}"

    # A call may be retried after a failed upload; replace only the two capture
    # inputs and leave the rest of the call memory untouched.
    for path in call_directory.glob("mic_raw.*"):
        if path != mic_destination:
            path.unlink(missing_ok=True)
    for path in call_directory.glob("system_raw.*"):
        if path != system_destination:
            path.unlink(missing_ok=True)

    try:
        mic_bytes = await _save_audio_upload(
            mic_audio,
            mic_destination,
            max_bytes,
        )
        system_bytes = await _save_audio_upload(
            system_audio,
            system_destination,
            max_bytes,
        )
    except HTTPException:
        mic_destination.unlink(missing_ok=True)
        system_destination.unlink(missing_ok=True)
        raise
    except Exception as error:
        mic_destination.unlink(missing_ok=True)
        system_destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=500,
            detail=f"Could not save the browser recording: {error}",
        ) from error

    call.duration_seconds = float(duration_seconds)
    call.status = CallStatus.PROCESSING
    call.failure_reason = None
    call_repository.save(call)

    record_product_event(
        user_id=user.id,
        event_name="recording_finished",
        call_id=call.id,
        properties={
            "duration_seconds": call.duration_seconds,
            "capture_mode": "browser",
            "mic_bytes": mic_bytes,
            "system_bytes": system_bytes,
        },
    )

    return {
        "call": call,
        "recording": {
            "mic": str(mic_destination),
            "system": str(system_destination),
            "duration_seconds": call.duration_seconds,
            "mic_bytes": mic_bytes,
            "system_bytes": system_bytes,
        },
    }


@app.post(
    "/calls/{call_id}/finish",
)
def finish_call_recording(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

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

    if not (
        recorder_manager
        .is_recording(
            call_id
        )
    ):
        call.status = (
            CallStatus.FAILED
        )

        call.failure_reason = (
            "recording_interrupted"
        )

        call_repository.save(
            call
        )

        raise HTTPException(
            status_code=409,
            detail=(
                "The recording session "
                "ended unexpectedly before "
                "it could be finished."
            ),
        )

    try:
        recording_result = (
            recorder_manager.finish(
                call_id
            )
        )

    except Exception as error:
        call.status = (
            CallStatus.FAILED
        )

        call.failure_reason = (
            "recording_finish_failed"
        )

        call_repository.save(
            call
        )

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

    call_repository.save(
        call
    )
    record_product_event(
        user_id=user.id,
        event_name="recording_finished",
        call_id=call.id,
        properties={"duration_seconds": call.duration_seconds},
    )

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
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    return {
        "call_id": call.id,
        "status": call.status,
        "is_recording": (
            call.status == CallStatus.RECORDING
            if config.capture_mode == "browser"
            else recorder_manager.is_recording(call_id)
        ),
        "is_paused": (
            call.status == CallStatus.PAUSED
            if config.capture_mode == "browser"
            else recorder_manager.is_paused(call_id)
        ),
        "elapsed_seconds": (
            call.duration_seconds
            if config.capture_mode == "browser"
            else recorder_manager.elapsed_seconds(call_id)
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
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    call_directory = (
        call_repository
        .get_directory(
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

    mic_file = next(
        (path for path in call_directory.glob("mic_raw.*") if path.is_file()),
        None,
    )
    system_file = next(
        (path for path in call_directory.glob("system_raw.*") if path.is_file()),
        None,
    )

    if mic_file is None or system_file is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This call does not have "
                "a complete saved recording."
            ),
        )

    call.status = (
        CallStatus.PROCESSING
    )

    call.failure_reason = None

    call_repository.save(
        call
    )
    record_product_event(
        user_id=user.id,
        event_name="processing_started",
        call_id=call.id,
        properties={"duration_seconds": call.duration_seconds},
    )

    try:
        result = processing_service.process(
            call,
            local_speaker_name=user.name,
        )
        record_product_event(
            user_id=user.id,
            event_name="processing_completed",
            call_id=call.id,
            properties={"duration_seconds": call.duration_seconds},
        )
        record_product_event(
            user_id=user.id,
            event_name="conversation_saved",
            call_id=call.id,
            properties={"status": call.status.value},
        )
        return result

    except Exception as error:
        latest_call = (
            call_repository.get(
                call_id,
                user_id=user.id,
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
        record_product_event(
            user_id=user.id,
            event_name="processing_failed",
            call_id=call_id,
            properties={"error": str(error)[:500]},
        )

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        ) from error


@app.post(
    "/calls/{call_id}/follow-up",
)
def generate_call_follow_up(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if call.status != CallStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=(
                "Follow-up is only available "
                "for completed conversations."
            ),
        )

    call_directory = (
        call_repository.get_directory(
            call_id
        )
    )

    recipient_name = None
    notes_file = call_directory / "notes.json"

    if notes_file.exists():
        try:
            notes = json.loads(
                notes_file.read_text(
                    encoding="utf-8"
                )
            )
        except (json.JSONDecodeError, OSError):
            notes = {}

        participants = notes.get(
            "participants",
            [],
        )

        if isinstance(participants, list):
            for participant in participants:
                if not isinstance(participant, dict):
                    continue

                role = str(
                    participant.get("role", "") or ""
                ).casefold()

                name = str(
                    participant.get("name", "") or ""
                ).strip()

                if role == "them" and name:
                    recipient_name = name
                    break

    ai_context = set_ai_context(
        user_id=user.id,
        call_id=call.id,
        operation="follow_up",
    )

    try:
        message = generate_follow_up(
            call_directory=call_directory,
            call_title=call.title,
            recipient_name=recipient_name,
        )
        record_product_event(
            user_id=user.id,
            event_name="follow_up_generated",
            call_id=call.id,
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
    finally:
        reset_ai_context(ai_context)

    return {
        "call_id": call_id,
        "recipient_name": recipient_name,
        "message": message,
    }


@app.get(
    "/calls/{call_id}/feedback",
    response_model=FeedbackResponse | None,
)
def get_call_feedback(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if call.status != CallStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Feedback is only available for completed conversations.",
        )

    return get_feedback(
        user_id=user.id,
        call_id=call_id,
    )


@app.post(
    "/calls/{call_id}/feedback",
    response_model=FeedbackResponse,
)
def submit_call_feedback(
    call_id: str,
    request: SubmitFeedbackRequest,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    if call.status != CallStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Feedback is only available for completed conversations.",
        )

    try:
        return submit_feedback(
            user_id=user.id,
            call_id=call_id,
            rating=request.rating,
            comment=request.comment,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@app.get(
    "/analytics",
    response_model=AnalyticsResponse,
)
def get_analytics(
    days: int = Query(default=30, ge=1, le=365),
    user=Depends(get_current_user),
):
    return build_analytics_snapshot(
        user_id=user.id,
        days=days,
    )


@app.get(
    "/analytics/admin",
    response_model=AnalyticsResponse,
)
def get_admin_analytics(
    days: int = Query(default=30, ge=1, le=365),
    user=Depends(get_current_user),
):
    if not is_analytics_admin(user.email):
        raise HTTPException(
            status_code=403,
            detail="Analytics admin access is not enabled for this account.",
        )

    return build_analytics_snapshot(
        user_id=None,
        days=days,
    )


@app.get(
    "/calls/{call_id}/transcript",
)
def get_call_transcript(
    call_id: str,
    user=Depends(get_current_user),
):
    require_call(
        call_id,
        user,
    )

    call_directory = (
        call_repository
        .get_directory(
            call_id
        )
    )

    transcript_file = (
        call_directory
        / "combined_transcript.txt"
    )

    if (
        not transcript_file.exists()
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Transcript not available."
            ),
        )

    return {
        "call_id": call_id,
        "transcript": (
            transcript_file
            .read_text(
                encoding="utf-8"
            )
        ),
    }


@app.get(
    "/calls/{call_id}/notes",
)
def get_call_notes(
    call_id: str,
    user=Depends(get_current_user),
):
    call = require_call(
        call_id,
        user,
    )

    call_directory = (
        call_repository
        .get_directory(
            call_id
        )
    )

    notes_file = (
        call_directory
        / "notes.json"
    )

    if (
        not notes_file.exists()
    ):
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
    user,
) -> Call:
    call = (
        call_repository.get(
            call_id,
            user_id=user.id,
        )
    )

    if call is None:
        raise HTTPException(
            status_code=404,
            detail="Call not found.",
        )

    return recover_stale_call(
        call
    )