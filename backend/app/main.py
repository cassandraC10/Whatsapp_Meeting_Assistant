from fastapi import FastAPI, HTTPException, status

from backend.app.models import (
    Call,
    CreateCallRequest,
)
from backend.app.repository import CallRepository


app = FastAPI(
    title="TCA API",
    description=(
        "Backend API for TCA — "
        "The Call Assistant"
    ),
    version="0.2.0",
)


call_repository = CallRepository()


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
    return call_repository.list_all()


@app.get(
    "/calls/{call_id}",
    response_model=Call,
)
def get_call(
    call_id: str,
):
    call = call_repository.get(
        call_id
    )

    if not call:
        raise HTTPException(
            status_code=404,
            detail="Call not found.",
        )

    return call