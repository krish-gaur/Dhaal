"""
Plan and loans routes.

Plan steps are derived entirely from deterministic server-side rules.
The LLM is never called here.
APR is always from IRR, never from the nominal rate.
Loan offers are labelled synthetic in every response.
"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from db.session_store import get_clauses, get_db, get_session
from engine.loans import (
    AffordabilityContext,
    LoanOffer,
    compute_affordability,
    compute_loan_metrics,
)
from routes.schemas import ActionStep, LoanMetricsResponse, PlanResponse

router = APIRouter(prefix="/api/session", tags=["plan"])

import os

_FIXTURES_DIR = Path(
    os.getenv("DHAAL_FIXTURES_DIR")
    or str(Path(__file__).parent.parent.parent.parent / "fixtures")
)

# Draft GRO message template (filled with fixture values; live mode would use session data)
_GRO_TEMPLATE = """To,
The Grievance Redressal Officer,
Suraksha General Insurance Co. Ltd. [FICTIONAL]

Subject: Request for written confirmation of apportionment base — Policy No. [YOUR POLICY NUMBER]

Dear Sir/Madam,

I am writing with reference to my health insurance policy. I am planning a hospitalisation
and wish to understand exactly which charges will be subject to proportionate deduction
in the event that my room rent exceeds the eligible limit.

Specifically, I request written confirmation of:
1. The eligible room rent limit under my policy.
2. The exact list of charges classified as "associated medical expenses" for the purpose
   of proportionate deduction as per Clause 3.2 of the policy.

I understand that this interpretation may significantly affect my out-of-pocket costs.
I request a written response within 14 days, as per IRDAI Regulation 17(1)(b).

If I do not receive a satisfactory response within 14 days, I will escalate to
Bima Bharosa (IRDAI Integrated Grievance Management System) at bimabharosa.irdai.gov.in.

Yours sincerely,
[YOUR NAME]
[YOUR POLICY NUMBER]
[DATE]

Note: This is a draft. Check every figure and reference before you send it.
"""


def _load_loan_offers() -> list[LoanOffer]:
    path = _FIXTURES_DIR / "loan_offers.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Loan offers fixture not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    offers: list[LoanOffer] = []
    for o in data["offers"]:
        offers.append(
            LoanOffer(
                label=o["label"],
                principal=Decimal(o["principal"]),
                nominal_rate_pa=Decimal(o["nominal_rate_pa"]),
                tenor_months=int(o["tenor_months"]),
                processing_fee=Decimal(o["processing_fee"]),
                gst_on_fee=Decimal(o["gst_on_fee"]),
                credit_life_premium=Decimal(o["credit_life_premium"]),
            )
        )
    return offers


def _load_affordability() -> AffordabilityContext:
    path = _FIXTURES_DIR / "income_history.json"
    if not path.exists():
        raise HTTPException(status_code=500, detail="Income history fixture not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return AffordabilityContext(
        income_months=[Decimal(str(m)) for m in data["months"]],
        essentials=Decimal(str(data["essentials"])),
        existing_emi=Decimal(str(data["existing_emi"])),
        savings=Decimal(str(data["savings"])),
    )


def _pct_str(value: Decimal) -> str:
    return f"{float(value * 100):.2f}% p.a."


@router.get("/{session_id}/loans", response_model=list[LoanMetricsResponse])
def get_loans(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> list[LoanMetricsResponse]:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    offers = _load_loan_offers()
    affordability_ctx = _load_affordability()
    aff = compute_affordability(affordability_ctx)

    results: list[LoanMetricsResponse] = []
    for offer in offers:
        m = compute_loan_metrics(offer, aff)
        results.append(
            LoanMetricsResponse(
                label=m.offer.label,
                principal=str(m.offer.principal),
                emi=str(m.emi),
                net_disbursed=str(m.net_disbursed),
                total_repayment=str(m.total_repayment),
                total_interest=str(m.total_interest),
                total_cash_out=str(m.total_cash_out),
                apr_nominal=str(m.apr_nominal),
                apr_effective=str(m.apr_effective),
                emi_pct_of_mean=str(m.emi_pct_of_mean),
                emi_pct_of_lean=str(m.emi_pct_of_lean),
                free_cash_avg_month=str(m.free_cash_avg_month),
                free_cash_lean_month=str(m.free_cash_lean_month),
                synthetic=True,
            )
        )
    return results


@router.get("/{session_id}/plan", response_model=PlanResponse)
def get_plan(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> PlanResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    clauses = get_clauses(db, session_id)
    clause_status: dict[str, str] = {}
    for c in clauses:
        if c.rule_type:
            clause_status[c.rule_type] = c.status

    unresolved_items: list[str] = []
    if clause_status.get("apportionment_base") not in ("verified", "user_confirmed"):
        unresolved_items.append("Apportionment base — 'associated medical expenses' undefined")
    if clause_status.get("waiting_period") not in ("verified", "user_confirmed"):
        unresolved_items.append("Waiting period — continuity credit not confirmed")

    # Deterministic plan steps (server-side rules, not LLM)
    steps: list[ActionStep] = [
        ActionStep(
            rank=1,
            title="Confirm your continuity credit",
            why=(
                "Your specified-disease waiting period is 24 months. "
                "If your policy has been active for 24+ months (or ported continuously), "
                "the insurer must cover this claim. Confirming this is worth ₹81,333."
            ),
            effort="Retrieve your renewal receipt or policy inception letter.",
            clause_id="c_waiting_period_01",
            rupee_value="81333",
        ),
        ActionStep(
            rank=2,
            title="Ask the hospital for a room within ₹3,000/day",
            why=(
                "Your policy covers room rent up to 1% of sum insured (₹3,000/day). "
                "Choosing a room at or below this limit eliminates the proportionate "
                "deduction entirely, saving ₹29,167."
            ),
            effort="Ask the admissions desk for a room at ₹3,000/day or below.",
            clause_id="c_room_rent_01",
            rupee_value="29167",
        ),
        ActionStep(
            rank=3,
            title="Get written confirmation of your apportionment base",
            why=(
                "The phrase 'associated medical expenses' in Clause 3.2 is undefined. "
                "Whether diagnostics are included changes your out-of-pocket by up to ₹24,667. "
                "Write to the insurer's Grievance Redressal Officer before admission."
            ),
            effort="Send the draft message below to the insurer's GRO.",
            clause_id="c_apportionment_01",
            rupee_value="24667",
        ),
        ActionStep(
            rank=4,
            title="Do not take Offer A or Offer C",
            why=(
                "Both Offer A (EMI ₹4,001) and Offer C (EMI ₹5,263) leave a negative balance "
                "in your worst income month. Offer B (EMI ₹2,763) is the least bad option — "
                "but it also leaves you short by ₹2,963 in a lean month."
            ),
            effort="Review the loan table on the previous screen.",
            clause_id=None,
            rupee_value="0",
        ),
    ]

    return PlanResponse(
        steps=steps,
        draft_message=_GRO_TEMPLATE,
        unresolved_items=unresolved_items,
    )
