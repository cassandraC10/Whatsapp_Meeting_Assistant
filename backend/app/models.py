from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CallStatus(str, Enum):
    CREATED = "created"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateCallRequest(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=120,
    )


class Call(BaseModel):
    id: str
    title: str
    created_at: datetime
    duration_seconds: float = 0
    status: CallStatus = CallStatus.CREATED
    failure_reason: str | None = None