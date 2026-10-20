"""Session creation, detail, and deletion routes."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import (
    create_session,
    delete_session,
    get_clauses,
    get_db,
    get_document,
    get_session,
)
from routes.schemas import (
    CreateSessionRequest,
    DeleteSessionResponse,
    MaterialFactState,
    SessionDetailResponse,
    SessionResponse,
)
from routes.simulate import _DECIDED_STATUSES, material_fact_states

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", response_model=SessionResponse)
def create_new_session(
    body: CreateSessionRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionResponse:
    mode: Literal["fixture", "live"] = "fixture" if body.use_fixture else "live"
    result = create_session(db, mode=mode, goal=body.goal)
    return SessionResponse(session_id=result["session_id"], mode=mode)


@router.get("/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionDetailResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    document = get_document(db, session_id)
    states = material_fact_states(get_clauses(db, session_id))
    mode: Literal["fixture", "live"] = "fixture" if session.mode == "fixture" else "live"
    return SessionDetailResponse(
        session_id=session.id,
        mode=mode,
        goal=session.goal,
        created_at=session.created_at,
        has_document=document is not None,
        simulation_ready=document is not None
        and all(status in _DECIDED_STATUSES for status in states.values()),
        material_facts=[
            MaterialFactState(rule_type=rule_type, status=status)
            for rule_type, status in states.items()
        ],
    )


@router.post("/{session_id}/delete", response_model=DeleteSessionResponse)
def delete_session_route(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> DeleteSessionResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    result = delete_session(db, session_id)
    counts_obj = result.get("counts", {})
    counts: dict[str, int] = {}
    if isinstance(counts_obj, dict):
        counts = {str(k): int(v) for k, v in counts_obj.items() if isinstance(v, int)}
    return DeleteSessionResponse(
        deleted=bool(result.get("deleted")),
        verified=bool(result.get("verified")),
        counts=counts,
    )
