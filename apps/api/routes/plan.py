"""
Plan and loans routes.

Plan steps are derived from deterministic engine runs over the session's
own clauses and the hospital estimate — every rupee figure is computed,
never hard-coded. The LLM is never called here.

APR is always from IRR, never from the nominal rate.
Loan offers are labelled synthetic in every response.
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from db.models import ClauseRow
from db.session_store import get_clauses, get_db, get_session
from engine.claim import simulate_claim
from engine.loans import LoanMetrics, compute_affordability, compute_loan_metrics
from engine.rules import ApportionmentBase, ChargeItem, ClaimInputs, ClaimResult, PolicyRules
from routes.fixture_data import (
    load_affordability_ctx,
    load_estimate_raw,
    load_loan_offers,
)
from routes.schemas import ActionStep, LoanMetricsResponse, PlanResponse, SimulationAssumptions
from routes.simulate import _build_policy_rules, _clause_params

router = APIRouter(prefix="/api/session", tags=["plan"])


def _shift_months(d: date, months: int) -> date:
    """`d` advanced by whole calendar months, day clamped to month length."""
    total = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

# Draft GRO message template. The 14-day grievance-resolution window and the
# Bima Bharosa escalation route are per IRDAI's Master Circular on Protection
# of Policyholders' Interests, 2024. It stays a draft: the user must check
# every figure and reference before sending.
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
   of proportionate deduction under the policy wording.

I understand that this interpretation may significantly affect my out-of-pocket costs.
I request a written response within 14 days, as required for grievance resolution under
IRDAI's Master Circular on Protection of Policyholders' Interests, 2024.

If I do not receive a satisfactory response within 14 days, I will escalate to
Bima Bharosa (IRDAI's grievance portal) at bimabharosa.irdai.gov.in.

Yours sincerely,
[YOUR NAME]
[YOUR POLICY NUMBER]
[DATE]

Note: This is a draft. Check every figure and reference before you send it.
"""


def _whole(amount: Decimal) -> int:
    """Round to whole rupees (display only; HALF_UP)."""
    from decimal import ROUND_HALF_UP

    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _inr(amount: Decimal) -> str:
    """Format an amount with Indian digit grouping, e.g. ₹81,333."""
    n = _whole(amount)
    sign = "−" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return f"{sign}₹{','.join(parts + [tail])}"


def _estimate_inputs(estimate: dict, room_rate: Decimal, month: int) -> ClaimInputs:  # type: ignore[type-arg]
    """
    ClaimInputs for the fixture estimate at a given room rate and policy month.

    Changing the room rate keeps the hospital's total estimate unchanged
    (package pricing): the room difference moves to surgeon fees so the
    charge lines still sum to the gross bill.
    """
    nights = int(estimate["nights"])
    new_room = room_rate * nights
    charges: list[ChargeItem] = []
    room_delta: Decimal | None = None
    raw_charges = estimate["charges"]
    for c in raw_charges:
        if c.get("nights") is not None:
            room_delta = Decimal(str(c["amount"])) - new_room
            break
    for c in raw_charges:
        amount = Decimal(str(c["amount"]))
        charge_nights = int(c["nights"]) if c.get("nights") is not None else None
        if charge_nights is not None:
            amount = new_room
        elif room_delta is not None and "surgeon" in str(c["name"]).lower():
            amount += room_delta
        charges.append(ChargeItem(name=str(c["name"]), amount=amount, nights=charge_nights))
    facts = estimate["policy_facts"]
    days_since: int | None = None
    inception_raw = facts.get("inception_date")
    if inception_raw:
        # Days of cover corresponding to `month` whole months from the
        # fixture inception date — so day-based (initial) waiting
        # periods resolve consistently with the month figure.
        inception = date.fromisoformat(str(inception_raw))
        days_since = (_shift_months(inception, month) - inception).days
    return ClaimInputs(
        gross_bill=Decimal(str(estimate["gross_bill"])),
        charges=charges,
        room_rate_per_night=room_rate,
        nights=nights,
        policy_month_at_admit=month,
        remaining_sum_insured=Decimal(str(facts["sum_insured"])),
        condition_tag=str(facts["condition_tag"]) if facts.get("condition_tag") else None,
        is_pre_existing=False,
        days_since_inception=days_since,
    )


def _room_cap_per_day(rules: PolicyRules) -> Decimal | None:
    if rules.room_limit is None:
        return None
    if rules.room_limit.basis == "pct_sum_insured_per_day":
        return rules.sum_insured * rules.room_limit.value
    return rules.room_limit.value


def _derive_steps(
    clauses: list[ClauseRow],
    rules: PolicyRules,
    estimate: dict,  # type: ignore[type-arg]
    loan_metrics: list[LoanMetrics],
) -> list[ActionStep]:
    """Compute ranked action steps from engine runs. No hard-coded figures."""
    facts = estimate["policy_facts"]
    base_month = int(facts["policy_month_at_admit"])
    billed_rate = Decimal(str(estimate["room_rate_per_night"]))

    clause_by_type: dict[str, ClauseRow] = {
        c.rule_type: c for c in clauses if c.rule_type
    }

    steps: list[ActionStep] = []

    # --- Step candidate 1: continuity credit (waiting period) -------------
    # Only the condition-scoped (specified-disease) period drives this
    # step — never the PED or initial wait. The clause cited is the
    # specified waiting clause itself.
    condition_tag = (
        str(facts["condition_tag"]) if facts.get("condition_tag") else None
    )
    waiting: ClauseRow | None = None
    for clause in clauses:
        if clause.rule_type != "waiting_period":
            continue
        params = _clause_params(clause)
        if params.get("scope", "specified") != "specified":
            continue
        conditions = [
            c.strip() for c in params.get("conditions", "").split(",") if c.strip()
        ]
        if conditions and condition_tag and condition_tag not in conditions:
            continue
        waiting = clause
        break
    served_month: int | None = None
    specified = [
        wp
        for wp in rules.waiting_periods
        if wp.scope == "specified"
        and (not wp.conditions or (condition_tag and condition_tag in wp.conditions))
    ]
    if waiting is not None and specified:
        required = max(wp.months_required for wp in specified)
        served_month = max(base_month, required)
        blocked = simulate_claim(rules, _estimate_inputs(estimate, billed_rate, base_month))
        served = simulate_claim(rules, _estimate_inputs(estimate, billed_rate, served_month))
        value = served.insurer_payment - blocked.insurer_payment
        if value > 0:
            steps.append(
                ActionStep(
                    rank=0,
                    title="Confirm your continuity credit",
                    why=(
                        f"The specified-disease waiting period in your policy is "
                        f"{required} months, and this admission falls at month "
                        f"{base_month}. If your earlier cover ran continuously into "
                        f"this policy, the waiting period would count as served. On "
                        f"this estimate that difference is worth {_inr(value)} — the "
                        f"insurer still assesses the full claim on its merits."
                    ),
                    effort="Retrieve your renewal receipt or policy inception letter.",
                    clause_id=waiting.id,
                    rupee_value=str(_whole(value)),
                )
            )

    # --- Step candidate 2: choose a room within the cap -------------------
    room_clause = clause_by_type.get("room_rent_limit")
    cap = _room_cap_per_day(rules)
    if room_clause is not None and cap is not None and cap < billed_rate:
        month_for_room = served_month if served_month is not None else base_month
        above = simulate_claim(rules, _estimate_inputs(estimate, billed_rate, month_for_room))
        at_cap = simulate_claim(rules, _estimate_inputs(estimate, cap, month_for_room))
        saving = above.out_of_pocket - at_cap.out_of_pocket
        if saving > 0:
            steps.append(
                ActionStep(
                    rank=0,
                    title=f"Ask the hospital for a room within {_inr(cap)}/day",
                    why=(
                        f"Your policy covers room rent up to {_inr(cap)} per day. "
                        f"The estimate uses {_inr(billed_rate)} per day, which also "
                        f"triggers a proportionate cut to other charges. A room at "
                        f"or below the limit reduces what you pay by {_inr(saving)} "
                        f"on this estimate."
                    ),
                    effort=f"Ask the admissions desk for a room at {_inr(cap)}/day or below.",
                    clause_id=room_clause.id,
                    rupee_value=str(_whole(saving)),
                )
            )

    # --- Step candidate 3: written confirmation of apportionment base ------
    apportionment = clause_by_type.get("apportionment_base")
    if apportionment is not None:
        scope = _clause_params(apportionment).get("scope", "unresolved")
        if scope == "unresolved" or rules.apportionment_base == ApportionmentBase.UNRESOLVED:
            month_for_ap = served_month if served_month is not None else base_month
            worked = simulate_claim(rules, _estimate_inputs(estimate, billed_rate, month_for_ap))
            impact = _proportionate_impact(worked)
            if impact > 0:
                steps.append(
                    ActionStep(
                        rank=0,
                        title="Get written confirmation of your apportionment base",
                        why=(
                            "The phrase 'associated medical expenses' is not fully "
                            "defined in the policy. Which charges it covers changes "
                            f"what you pay by up to {_inr(impact)} on this estimate. "
                            "Ask the insurer's Grievance Redressal Officer in writing "
                            "before admission, using the draft below."
                        ),
                        effort="Send the draft message below to the insurer's GRO.",
                        clause_id=apportionment.id,
                        rupee_value=str(_whole(impact)),
                    )
                )

    # --- Step candidate 4: loan warning ------------------------------------
    unaffordable = [m for m in loan_metrics if m.free_cash_lean_month < 0]
    if unaffordable:
        details = "; ".join(
            f"Offer {m.offer.label} (EMI {_inr(m.emi)}) leaves you "
            f"{_inr(-m.free_cash_lean_month)} short"
            for m in unaffordable
        )
        steps.append(
            ActionStep(
                rank=0,
                title="Do not rely on these loans for the gap",
                why=(
                    f"In your worst income month: {details}. None of these loans "
                    "is serviceable in your worst month."
                ),
                effort="Review the loan table on the previous screen.",
                clause_id=None,
                rupee_value="0",
            )
        )

    # Rank by computed rupee value, highest first; the loan warning (₹0) last.
    steps.sort(key=lambda s: Decimal(s.rupee_value), reverse=True)
    return [
        ActionStep(
            rank=i + 1,
            title=s.title,
            why=s.why,
            effort=s.effort,
            clause_id=s.clause_id,
            rupee_value=s.rupee_value,
        )
        for i, s in enumerate(steps)
    ]


def _proportionate_impact(result: ClaimResult) -> Decimal:
    """Largest plausible proportionate deduction in a simulation result."""
    applied = sum(
        (d.amount for d in result.deductions if d.rule_id == "proportionate_deduction"),
        Decimal("0"),
    )
    if applied > 0:
        return applied
    for u in result.unresolved:
        if u.rule_type.value == "proportionate_deduction":
            return u.high_impact - u.low_impact
    return Decimal("0")


@router.get("/{session_id}/loans", response_model=list[LoanMetricsResponse])
def get_loans(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> list[LoanMetricsResponse]:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    aff = compute_affordability(load_affordability_ctx())
    results: list[LoanMetricsResponse] = []
    for offer in load_loan_offers():
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
    estimate = load_estimate_raw()
    facts = estimate["policy_facts"]

    # Worked assumptions for the plan's engine runs. The apportionment choice
    # only matters when the clause itself carries no confirmed scope — the
    # builder gives a confirmed clause scope precedence.
    assumptions = SimulationAssumptions(
        policy_month_at_admit=int(facts["policy_month_at_admit"]),
        remaining_sum_insured=str(facts["sum_insured"]),
        sum_insured=str(facts["sum_insured"]),
        non_payable_total=str(estimate["non_payable_total"]),
        apportionment_base="surgeon_ot_diagnostics",
        continuity_confirmed=False,
        condition_tag=str(facts["condition_tag"]) if facts.get("condition_tag") else None,
        is_pre_existing=False,
        inception_date=str(facts["inception_date"]) if facts.get("inception_date") else None,
        admission_date=str(estimate["admission_date"]) if estimate.get("admission_date") else None,
    )
    rules = _build_policy_rules(clauses, assumptions)

    aff = compute_affordability(load_affordability_ctx())
    loan_metrics = [compute_loan_metrics(o, aff) for o in load_loan_offers()]

    steps = _derive_steps(clauses, rules, estimate, loan_metrics)

    labels = {
        "room_rent_limit": "Room rent limit",
        "waiting_period": "Waiting period",
        "non_payable": "Non-payable items",
        "apportionment_base": "Apportionment base — 'associated medical expenses'",
    }
    unresolved_items: list[str] = []
    for clause in clauses:
        if clause.rule_type in labels and clause.status not in ("verified", "user_confirmed"):
            unresolved_items.append(
                f"{labels[clause.rule_type]} — {clause.status.replace('_', ' ')}"
            )

    return PlanResponse(
        steps=steps,
        draft_message=_GRO_TEMPLATE,
        unresolved_items=unresolved_items,
    )
