"""Session creation and deletion routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import create_session, delete_session, get_db, get_session
from routes.schemas import (
    CreateSessionRequest,
    DeleteSessionResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", response_model=SessionResponse)
def create_new_session(
    body: CreateSessionRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionResponse:
    mode = "fixture" if body.use_fixture else "live"
    result = create_session(db, mode=mode, goal=body.goal)
    return SessionResponse(session_id=result["session_id"], mode=result["mode"])  # type: ignore[arg-type]


@router.post("/{session_id}/delete", response_model=DeleteSessionResponse)
def delete_session_route(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> DeleteSessionResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    result = delete_session(db, session_id)
    return DeleteSessionResponse(**result)
