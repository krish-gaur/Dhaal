"""
Audit route (Screen 5): what data the session holds, which engine ran,
what was sent to an AI provider, and a reproducible record of every run.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import get_clauses, get_db, get_document, get_runs, get_session
from routes.document import _provenance_response
from routes.schemas import AuditDocumentInfo, AuditResponse, AuditRunInfo
from routes.session import _policy_identity
from version import APP_VERSION

router = APIRouter(prefix="/api/session", tags=["audit"])


def _provider_name() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "fixture"


def _provider_disclosure(session_mode: str, provider: str) -> str:
    if session_mode == "fixture" or provider == "fixture":
        return (
            "Nothing was sent to an external AI provider. This session used "
            "the built-in sample (fixture) data only."
        )
    return (
        f"Policy page text was sent to the {provider} extraction provider to "
        "identify clauses. No figures were computed by the AI provider; all "
        "arithmetic is done by the local engine."
    )


@router.get("/{session_id}/audit", response_model=AuditResponse)
def get_audit(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> AuditResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    doc = get_document(db, session_id)
    document_info: AuditDocumentInfo | None = None
    if doc is not None:
        try:
            pages = json.loads(doc.text_content)
            pages_read = len(pages) if isinstance(pages, list) else doc.page_count
        except Exception:
            pages_read = doc.page_count
        document_info = AuditDocumentInfo(
            filename=doc.filename,
            page_count=doc.page_count,
            pages_read=pages_read,
            retention="Deleted when you delete this session. Nothing is kept after deletion.",
            provenance=_provenance_response(doc),
        )

    runs: list[AuditRunInfo] = []
    for run in get_runs(db, session_id):
        digest = hashlib.sha256(
            (run.inputs_json + "|" + run.result_json).encode("utf-8")
        ).hexdigest()
        insurer: str | None = None
        oop: str | None = None
        try:
            result = json.loads(run.result_json)
            if isinstance(result, dict):
                insurer = str(result["insurer_payment"]) if "insurer_payment" in result else None
                oop = str(result["out_of_pocket"]) if "out_of_pocket" in result else None
        except Exception:
            pass
        runs.append(
            AuditRunInfo(
                run_id=run.id,
                created_at=run.created_at,
                run_hash=f"sha256:{digest[:16]}",
                invariants_ok=bool(run.invariants_ok),
                insurer_payment=insurer,
                out_of_pocket=oop,
            )
        )

    clauses_by_status: dict[str, int] = {}
    for clause in get_clauses(db, session_id):
        clauses_by_status[clause.status] = clauses_by_status.get(clause.status, 0) + 1

    provider = _provider_name()
    mode: Literal["fixture", "live"] = "fixture" if session.mode == "fixture" else "live"
    return AuditResponse(
        session_id=session.id,
        mode=mode,
        policy=_policy_identity(session),
        document=document_info,
        engine_version=APP_VERSION,
        provider_name=provider,
        provider_disclosure=_provider_disclosure(session.mode, provider),
        runs=runs,
        clauses_by_status=clauses_by_status,
    )
