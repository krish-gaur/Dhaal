"""Session creation, detail, and deletion routes."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from db.models import SessionRow
from db.session_store import (
    create_session,
    delete_session,
    get_clauses,
    get_db,
    get_document,
    get_session,
)
from routes.catalogue import get_product, resolve_held_document
from routes.schemas import (
    CreateSessionRequest,
    DeleteSessionResponse,
    MaterialFactState,
    PolicyIdentity,
    SessionDetailResponse,
    SessionResponse,
)
from routes.simulate import _DECIDED_STATUSES, material_fact_states

router = APIRouter(prefix="/api/session", tags=["session"])


def _policy_identity(session: SessionRow) -> PolicyIdentity:
    """Build the API policy-identity block from a session row."""
    uin: str | None = None
    fictional = False
    if session.catalogue_product_id:
        product = get_product(session.catalogue_product_id)
        if product is not None:
            uin = product.get("uin")
            fictional = bool(product.get("fictional", False))
    return PolicyIdentity(
        insurer=session.insurer_name,
        product_name=session.product_name,
        product_id=session.catalogue_product_id,
        version=session.catalogue_version,
        uin=uin,
        fictional=fictional,
        identification_status=session.identification_status or "unidentified",
    )


@router.post("", response_model=SessionResponse)
def create_new_session(
    body: CreateSessionRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionResponse:
    # Policy-first: a catalogue selection pins the exact held wording.
    # The server validates it exists — an unknown product or an ambiguous
    # version is an error, never a silent substitution.
    if body.catalogue_product_id:
        product = get_product(body.catalogue_product_id)
        if product is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "That policy is not in the catalogue of wordings Dhaal "
                    "holds. Upload your policy PDF instead."
                ),
            )
        versions = product.get("versions", [])
        version = body.catalogue_version
        if version is None:
            if len(versions) > 1:
                available = ", ".join(str(v.get("version")) for v in versions)
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{product.get('product_name')} has multiple held "
                        f"versions ({available}). Choose the exact version "
                        "of your policy."
                    ),
                )
            version = str(versions[0]["version"]) if versions else None
        held = resolve_held_document(body.catalogue_product_id, version or "")
        result = create_session(
            db,
            mode="fixture",
            goal=body.goal,
            catalogue_product_id=held.product_id,
            catalogue_version=held.version,
            insurer_name=held.insurer,
            product_name=held.product_name,
            identification_status="catalogue_verified",
        )
        session = get_session(db, result["session_id"])
        return SessionResponse(
            session_id=result["session_id"],
            mode="fixture",
            policy=_policy_identity(session) if session else None,
        )

    if body.use_fixture:
        # Sample mode == the historical fictional sample policy, now
        # identified explicitly through the catalogue.
        held = resolve_held_document("suraksha-shield-health", "2022")
        result = create_session(
            db,
            mode="fixture",
            goal=body.goal,
            catalogue_product_id=held.product_id,
            catalogue_version=held.version,
            insurer_name=held.insurer,
            product_name=held.product_name,
            identification_status="catalogue_verified",
        )
        session = get_session(db, result["session_id"])
        return SessionResponse(
            session_id=result["session_id"],
            mode="fixture",
            policy=_policy_identity(session) if session else None,
        )

    # Upload path: the user may declare which policy they believe they
    # hold; the document is their upload and is NOT catalogue-verified.
    declared = bool(body.declared_insurer or body.declared_product)
    result = create_session(
        db,
        mode="live",
        goal=body.goal,
        insurer_name=body.declared_insurer,
        product_name=body.declared_product,
        identification_status="user_declared" if declared else "unidentified",
    )
    session = get_session(db, result["session_id"])
    return SessionResponse(
        session_id=result["session_id"],
        mode="live",
        policy=_policy_identity(session) if session else None,
    )


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
        policy=_policy_identity(session),
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
