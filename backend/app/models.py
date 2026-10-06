from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
)


class CallStatus(
    str,
    Enum,
):
    CREATED = "created"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateCallRequest(
    BaseModel
):
    title: str | None = Field(
        default=None,
        max_length=120,
    )


class UpdateCallRequest(
    BaseModel
):
    title: str = Field(
        min_length=1,
        max_length=120,
    )


class Call(
    BaseModel
):
    id: str
    user_id: str | None = None
    title: str
    created_at: datetime
    duration_seconds: float = 0
    status: CallStatus = (
        CallStatus.CREATED
    )
    failure_reason: str | None = None


class AskTCARequest(
    BaseModel
):
    question: str = Field(
        min_length=2,
        max_length=500,
    )

    call_id: str | None = Field(
        default=None,
        description=(
            "Optional call ID. "
            "When provided, TCA answers "
            "using only that conversation."
        ),
    )


class AskSource(
    BaseModel
):
    call_id: str
    title: str
    created_at: datetime
    snippet: str | None = None


class AskTCAResponse(
    BaseModel
):
    answer: str

    sources: list[
        AskSource
    ] = Field(
        default_factory=list
    )

    found_answer: bool = True

class TaskOwner(
    str,
    Enum,
):
    ME = "me"
    THEM = "them"


class Task(
    BaseModel
):
    id: str
    call_id: str
    owner: TaskOwner
    task: str = Field(
        min_length=1,
        max_length=500,
    )
    deadline: str | None = Field(
        default=None,
        max_length=200,
    )
    owner_name: str | None = Field(
        default=None,
        max_length=120,
    )
    completed: bool = False


class ParticipantRole(
    str,
    Enum,
):
    ME = "me"
    THEM = "them"


class Participant(
    BaseModel
):
    role: ParticipantRole
    name: str | None = Field(
        default=None,
        max_length=120,
    )
    source: str | None = Field(
        default=None,
        max_length=120,
    )


class SpeakerTurn(
    BaseModel
):
    speaker: ParticipantRole
    text: str = Field(
        min_length=1,
    )


class StructuredTranscript(
    BaseModel
):
    call_title: str | None = None
    participants: list[
        Participant
    ] = Field(
        default_factory=list
    )
    turns: list[
        SpeakerTurn
    ] = Field(
        default_factory=list
    )


class UpdateTaskRequest(
    BaseModel
):
    task: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    deadline: str | None = Field(
        default=None,
        max_length=200,
    )
    completed: bool | None = None


class TasksResponse(
    BaseModel
):
    call_id: str
    tasks: list[Task] = Field(
        default_factory=list
    )


class Person(BaseModel):
    id: str
    name: str
    conversation_count: int = 0


class PersonTask(BaseModel):
    id: str
    call_id: str
    task: str
    deadline: str | None = None
    completed: bool = False


class PersonDetail(BaseModel):
    id: str
    name: str
    conversation_count: int = 0
    open_next_steps: list[PersonTask] = Field(default_factory=list)
    recent_decisions: list[str] = Field(default_factory=list)
    conversations: list[Call] = Field(default_factory=list)


class PeopleResponse(BaseModel):
    people: list[Person] = Field(default_factory=list)




class FeedbackRating(
    str,
    Enum,
):
    HELPFUL = "helpful"
    NEEDS_WORK = "needs_work"


class SubmitFeedbackRequest(
    BaseModel
):
    rating: FeedbackRating
    comment: str | None = Field(
        default=None,
        max_length=2000,
    )


class FeedbackResponse(
    BaseModel
):
    id: str
    call_id: str
    rating: FeedbackRating
    comment: str | None = None
    created_at: datetime
    updated_at: datetime

class AuthUserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    onboarding_completed: bool = False


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    onboarding_completed: bool = True


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class CaptureHandoffResponse(BaseModel):
    code: str
    expires_at: int


class CaptureHandoffExchangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class AnalyticsEventCount(BaseModel):
    event_name: str
    count: int = 0


class AnalyticsOperationUsage(BaseModel):
    operation: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None


class AnalyticsOverview(BaseModel):
    active_days: int = 0
    conversation_events: int = 0
    capture_opens: int = 0
    recordings_started: int = 0
    recordings_finished: int = 0
    recording_seconds: float = 0
    searches: int = 0
    ask_questions: int = 0
    feedback_submitted: int = 0
    feedback_updated: int = 0
    feedback_helpful: int = 0
    feedback_needs_work: int = 0
    feedback_helpful_rate: float | None = None


class AnalyticsProcessing(BaseModel):
    started: int = 0
    completed: int = 0
    failed: int = 0
    success_rate: float | None = None


class AnalyticsAIUsage(BaseModel):
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    pricing_configured: bool = False
    model: str
    by_operation: list[AnalyticsOperationUsage] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    scope: str
    period_days: int
    generated_at: datetime
    overview: AnalyticsOverview
    processing: AnalyticsProcessing
    ai_usage: AnalyticsAIUsage
    events: list[AnalyticsEventCount] = Field(default_factory=list)
