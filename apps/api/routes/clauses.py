"""Clause listing and status update routes."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import (
    get_clauses,
    get_db,
    get_session,
    update_clause_status,
)
from routes.schemas import (
    ClauseResponse,
    PatchClauseRequest,
    RuleParamResponse,
    VerificationResponse,
)

router = APIRouter(prefix="/api/session", tags=["clauses"])


def _model_to_response(m: object) -> ClauseResponse:
    from db.models import ClauseRow
    assert isinstance(m, ClauseRow)
    params: dict[str, str] = {}
    if m.rule_params:
        try:
            params = json.loads(m.rule_params)
        except Exception:
            params = {}
    return ClauseResponse(
        clause_id=m.id,
        document_id=m.document_id,
        page=m.page,
        char_start=m.char_start,
        char_end=m.char_end,
        quote=m.quote,
        quote_hash=m.quote_hash,
        rule=RuleParamResponse(type=m.rule_type or "unknown", params=params),
        verification=VerificationResponse(
            schema_valid=bool(m.schema_valid),
            quote_found=bool(m.quote_found),
            numbers_supported=bool(m.numbers_ok),
            interpretation_status=m.status,
            reason=m.reason or "",
        ),
    )


@router.get("/{session_id}/clauses", response_model=list[ClauseResponse])
def list_clauses(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> list[ClauseResponse]:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    clauses = get_clauses(db, session_id)
    return [_model_to_response(c) for c in clauses]


@router.patch("/{session_id}/clauses/{clause_id}", response_model=ClauseResponse)
def patch_clause(
    session_id: str,
    clause_id: str,
    body: PatchClauseRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> ClauseResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    allowed = {"user_confirmed", "unknown"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Status must be one of: {sorted(allowed)}",
        )

    clause = update_clause_status(
        db,
        session_id=session_id,
        clause_id=clause_id,
        status=body.status,
        override=body.override,
    )
    if clause is None:
        raise HTTPException(status_code=404, detail="Clause not found")

    return _model_to_response(clause)
