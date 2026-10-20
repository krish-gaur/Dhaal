"""
Hospital estimate + affordability route (fixture demo inputs).

Serves the synthetic hospital estimate and the server-computed
affordability summary so the frontend never invents or computes figures.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import get_clauses, get_db, get_session
from engine.loans import compute_affordability
from routes.fixture_data import load_affordability_ctx, load_estimate_raw, load_income_raw
from routes.schemas import (
    AffordabilityResponse,
    ChargeItemRequest,
    EstimateResponse,
)
from routes.simulate import _APPLIED_STATUSES, _clause_params

router = APIRouter(prefix="/api/session", tags=["estimate"])


@router.get("/{session_id}/estimate", response_model=EstimateResponse)
def get_estimate(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> EstimateResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    estimate = load_estimate_raw()
    income = load_income_raw()
    aff_ctx = load_affordability_ctx()
    aff = compute_affordability(aff_ctx)
    policy_facts = estimate.get("policy_facts", {})
    sum_insured = Decimal(str(policy_facts["sum_insured"]))

    # Policy parameters for the scenario controls, read from this session's
    # applied clauses (never re-interpreted in the frontend).
    room_cap_per_day: Decimal | None = None
    waiting_months_required: int | None = None
    for clause in get_clauses(db, session_id):
        if clause.status not in _APPLIED_STATUSES:
            continue
        params = _clause_params(clause)
        if clause.rule_type == "room_rent_limit":
            basis = params.get("basis", "")
            value = Decimal(params.get("value", "0"))
            room_cap_per_day = (
                sum_insured * value if basis == "pct_sum_insured_per_day" else value
            )
        elif clause.rule_type == "waiting_period":
            waiting_months_required = int(params.get("months_required", "0"))

    return EstimateResponse(
        gross_bill=str(estimate["gross_bill"]),
        nights=int(estimate["nights"]),
        room_rate_per_night=str(estimate["room_rate_per_night"]),
        charges=[
            ChargeItemRequest(
                name=str(c["name"]),
                amount=str(c["amount"]),
                nights=int(c["nights"]) if c.get("nights") is not None else None,
            )
            for c in estimate["charges"]
        ],
        non_payable_total=str(estimate["non_payable_total"]),
        hospital_name=str(estimate["hospital_name"]),
        procedure=str(estimate["procedure"]),
        admission_date=str(estimate["admission_date"]),
        discharge_date=str(estimate["discharge_date"]),
        sum_insured=str(policy_facts["sum_insured"]),
        policy_month_at_admit=int(policy_facts["policy_month_at_admit"]),
        room_cap_per_day=str(room_cap_per_day) if room_cap_per_day is not None else None,
        waiting_months_required=waiting_months_required,
        affordability=AffordabilityResponse(
            months=[str(m) for m in income["months"]],
            month_labels=[str(m) for m in income["month_labels"]],
            mean_income=str(aff.mean),
            median_income=str(aff.median),
            lowest_income=str(aff.lowest_observed),
            avg_free_cash=str(aff.avg_free_cash),
            lean_free_cash=str(aff.lean_free_cash),
            emergency_runway_months=str(aff.emergency_runway_months),
            obligations_at_lean_pct=str(aff.obligations_at_lean_pct),
            savings=str(aff_ctx.savings),
            essentials=str(aff_ctx.essentials),
            existing_emi=str(aff_ctx.existing_emi),
            synthetic=True,
        ),
        synthetic=True,
    )
