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
