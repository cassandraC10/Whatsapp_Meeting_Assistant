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
    completed: bool = False


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
