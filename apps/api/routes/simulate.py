"""
Simulation and counterfactual routes.

The engine is called here. The LLM is never called here.
If invariants_ok == False, the route returns 500 — the result is NEVER rendered.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from db.models import ClauseRow
from db.session_store import get_clauses, get_db, get_session, save_simulation_run
from engine.attribution import FieldChange, counterfactual
from engine.claim import simulate_claim
from engine.rules import (
    ApportionmentBase,
    ChargeItem,
    ClaimInputs,
    ClaimResult,
    CoPayment,
    InvariantError,
    NonPayableList,
    PolicyRules,
    ProportionateRule,
    RoomLimit,
    RuleType,
    WaitingPeriod,
)
from routes.schemas import (
    CounterfactualRequest,
    CounterfactualResponse,
    DeductionResponse,
    SimulateRequest,
    SimulationAssumptions,
    SimulationResponse,
    UnresolvedRuleResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/session", tags=["simulate"])

_FIXTURE_WATERFALL = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]

# Material facts required before simulation is allowed (F-E11)
_MATERIAL_RULE_TYPES = (
    "room_rent_limit",
    "waiting_period",
    "non_payable",
    "apportionment_base",
)


_CONCRETE_BASES = {
    "room_related_only",
    "all_medical_expenses",
    "surgeon_ot_diagnostics",
}

_APPLIED_STATUSES = ("verified", "user_confirmed")
# A material fact is "decided" when the user has confirmed it, it is
# verified, or the user explicitly marked it unknown (F-E11).
_DECIDED_STATUSES = ("verified", "user_confirmed", "unknown")


def _clause_params(clause: ClauseRow) -> dict[str, str]:
    if not clause.rule_params:
        return {}
    try:
        parsed = json.loads(clause.rule_params)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def material_fact_states(clauses: list[ClauseRow]) -> dict[str, str]:
    """Status per material rule type; 'missing' when no clause exists."""
    states = {t: "missing" for t in _MATERIAL_RULE_TYPES}
    for clause in clauses:
        if clause.rule_type in states:
            states[clause.rule_type] = clause.status
    return states


def _build_policy_rules(
    clauses: list[ClauseRow], assumptions: SimulationAssumptions
) -> PolicyRules:
    """
    Build PolicyRules from session clauses and explicit assumptions.

    Honesty rules:
    - A rule is applied only when its clause is verified or user-confirmed.
      Anything else stays None / UNRESOLVED — never a silent default.
    - Sum insured and the non-payable billed total come from the request's
      explicit assumptions, not constants in this file.
    - Months elapsed is a claim input (ClaimInputs), not part of the rule.
    """
    room_limit: RoomLimit | None = None
    waiting_periods: list[WaitingPeriod] = []
    non_payable: NonPayableList | None = None
    co_payment: CoPayment | None = None
    deductible: Decimal | None = None
    apportionment_base = ApportionmentBase.UNRESOLVED
    # Worst-case bound for an unresolved apportionment comes from the
    # interpretations the extracted clause wording supports. Until an
    # apportionment clause says otherwise, all concrete bases remain
    # possible (the widest honest range).
    apportionment_candidates: tuple[ApportionmentBase, ...] = tuple(
        ApportionmentBase(v) for v in sorted(_CONCRETE_BASES)
    )
    has_proportionate = False

    for clause in clauses:
        rule_type = clause.rule_type or ""
        status = clause.status
        params = _clause_params(clause)
        applied = status in _APPLIED_STATUSES

        if rule_type == "proportionate_deduction" and applied:
            has_proportionate = True

        if rule_type == "apportionment_base" and status in _DECIDED_STATUSES:
            # The existence of this clause (in any decided state) is the
            # evidence that a proportionate deduction rule applies.
            has_proportionate = True
            # Evidence-linked range bounds: if the extracted clause records
            # which readings its wording supports, only those may bound an
            # unresolved range. An unknown candidate value is a data error
            # (422 via the handlers), never silently widened or narrowed.
            raw_candidates = params.get("candidates", "")
            if raw_candidates.strip():
                parsed: list[ApportionmentBase] = []
                for value in raw_candidates.split(","):
                    name = value.strip()
                    if not name:
                        continue
                    if name not in _CONCRETE_BASES:
                        raise ValueError(
                            f"Unknown apportionment candidate: '{name}'"
                        )
                    parsed.append(ApportionmentBase(name))
                if parsed:
                    apportionment_candidates = tuple(parsed)
            if status == "unknown":
                apportionment_base = ApportionmentBase.UNRESOLVED
            elif applied:
                scope = params.get("scope", "unresolved")
                if scope in _CONCRETE_BASES:
                    # A confirmed interpretation recorded on the clause wins.
                    apportionment_base = ApportionmentBase(scope)
                else:
                    # Clause confirmed but its own scope is unresolved: the
                    # interpretation is the user's explicit simulation choice.
                    apportionment_base = ApportionmentBase(
                        assumptions.apportionment_base
                    )

        if not applied:
            continue

        if rule_type == "room_rent_limit":
            basis = params.get("basis", "")
            if basis not in ("pct_sum_insured_per_day", "fixed_per_day"):
                raise ValueError(f"Unknown room limit basis: '{basis}'")
            room_limit = RoomLimit(
                basis=basis,  # type: ignore[arg-type]
                value=Decimal(params.get("value", "0")),
            )

        elif rule_type == "waiting_period":
            waiting_periods.append(
                WaitingPeriod(
                    disease_type=params.get("disease_type", "specified_disease"),
                    months_required=int(params.get("months_required", "0")),
                )
            )

        elif rule_type == "non_payable":
            items = [i.strip() for i in params.get("items", "").split(",") if i.strip()]
            # The policy says WHICH items; the billed total is an explicit
            # input. Without it the deduction is unknown, not invented.
            if assumptions.non_payable_total is not None:
                non_payable = NonPayableList(
                    items=items,
                    total=Decimal(assumptions.non_payable_total),
                )

        elif rule_type == "co_payment":
            co_payment = CoPayment(pct=Decimal(params.get("pct", "0")))

        elif rule_type == "deductible":
            deductible = Decimal(params.get("amount", "0"))

    return PolicyRules(
        sum_insured=Decimal(assumptions.sum_insured),
        waterfall=_FIXTURE_WATERFALL,
        room_limit=room_limit,
        waiting_periods=waiting_periods,
        non_payable=non_payable,
        co_payment=co_payment,
        deductible=deductible,
        proportionate_deduction=(
            ProportionateRule(trigger="room_above_cap") if has_proportionate else None
        ),
        apportionment_base=apportionment_base,
        apportionment_candidates=apportionment_candidates,
    )


def _build_claim_inputs(body: SimulateRequest, rules: PolicyRules) -> ClaimInputs:
    charges = [
        ChargeItem(
            name=c.name,
            amount=Decimal(c.amount),
            nights=c.nights,
        )
        for c in body.charges
    ]
    # Months elapsed is an explicit input. The legacy continuity flag means
    # "treat the waiting period as served": raise the effective month to the
    # requirement, never above what the user already claims.
    effective_month = body.assumptions.policy_month_at_admit
    if body.assumptions.continuity_confirmed and rules.waiting_periods:
        required = max(wp.months_required for wp in rules.waiting_periods)
        effective_month = max(effective_month, required)
    return ClaimInputs(
        gross_bill=Decimal(body.gross),
        charges=charges,
        room_rate_per_night=Decimal(body.room_rate_per_night),
        nights=body.nights,
        policy_month_at_admit=effective_month,
        remaining_sum_insured=Decimal(body.assumptions.remaining_sum_insured),
    )


def _result_to_response(result: ClaimResult) -> SimulationResponse:
    return SimulationResponse(
        gross_bill=str(result.gross_bill),
        non_payable_total=str(result.non_payable_total),
        admissible=str(result.admissible),
        deductions=[
            DeductionResponse(
                name=d.name,
                amount=str(d.amount),
                basis=d.basis,
                rule_id=d.rule_id,
                citation=d.citation,
            )
            for d in result.deductions
        ],
        insurer_payment=str(result.insurer_payment),
        out_of_pocket=str(result.out_of_pocket),
        remaining_sum_insured=str(result.remaining_sum_insured),
        unresolved=[
            UnresolvedRuleResponse(
                rule_type=u.rule_type.value,
                reason=u.reason,
                low_impact=str(u.low_impact),
                high_impact=str(u.high_impact),
            )
            for u in result.unresolved
        ],
        range_low=str(result.range_low) if result.range_low is not None else None,
        range_high=str(result.range_high) if result.range_high is not None else None,
        invariants_ok=result.invariants_ok,
    )


def _check_simulation_gate(clauses: list[ClauseRow]) -> list[str]:
    """
    Material facts blocking simulation (F-E11).

    A fact blocks simulation when its clause is missing, unverified, or
    conflicting. Verified, user-confirmed, and explicitly-unknown facts do
    not block — unknown widens the result to a range instead.
    """
    states = material_fact_states(clauses)
    return [
        rule_type.replace("_", " ")
        for rule_type, status in states.items()
        if status not in _DECIDED_STATUSES
    ]


@router.post("/{session_id}/simulate", response_model=SimulationResponse)
def run_simulation(
    session_id: str,
    body: SimulateRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> SimulationResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    clauses = get_clauses(db, session_id)
    missing = _check_simulation_gate(clauses)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Confirm or mark unknown: {', '.join(missing)}",
        )

    try:
        rules = _build_policy_rules(clauses, body.assumptions)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    inputs = _build_claim_inputs(body, rules)

    try:
        result = simulate_claim(rules, inputs)
    except InvariantError as e:
        logger.error("Invariant violation in session %s: %s", session_id, e)
        raise HTTPException(
            status_code=500,
            detail="An internal calculation error occurred. The result has been blocked.",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    if not result.invariants_ok:
        logger.error("invariants_ok=False in session %s", session_id)
        raise HTTPException(
            status_code=500,
            detail="Calculation invariant violated. Result blocked.",
        )

    # Persist run (without PII — numeric inputs, assumptions, and results)
    save_simulation_run(
        db,
        session_id=session_id,
        inputs={
            "gross": body.gross,
            "nights": body.nights,
            "room_rate_per_night": body.room_rate_per_night,
            "policy_month_at_admit": inputs.policy_month_at_admit,
            "remaining_sum_insured": body.assumptions.remaining_sum_insured,
            "sum_insured": body.assumptions.sum_insured,
            "non_payable_total": body.assumptions.non_payable_total,
            "apportionment_base": rules.apportionment_base.value,
        },
        result={
            "insurer_payment": str(result.insurer_payment),
            "out_of_pocket": str(result.out_of_pocket),
            "range_low": str(result.range_low) if result.range_low is not None else None,
            "range_high": str(result.range_high) if result.range_high is not None else None,
            "unresolved_count": len(result.unresolved),
        },
        invariants_ok=result.invariants_ok,
    )

    return _result_to_response(result)


_INT_CHANGE_FIELDS = {"policy_month_at_admit", "nights"}
_MONEY_CHANGE_FIELDS = {"room_rate_per_night", "gross_bill", "remaining_sum_insured"}


def _coerce_change_value(field: str, value: object) -> object:
    """Coerce a JSON counterfactual value to the engine's field type."""
    if field in _INT_CHANGE_FIELDS:
        return int(str(value))
    if field in _MONEY_CHANGE_FIELDS:
        return Decimal(str(value))
    return value


@router.post("/{session_id}/counterfactual", response_model=CounterfactualResponse)
def run_counterfactual(
    session_id: str,
    body: CounterfactualRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> CounterfactualResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    clauses = get_clauses(db, session_id)
    try:
        rules = _build_policy_rules(clauses, body.base.assumptions)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    inputs = _build_claim_inputs(body.base, rules)

    change = FieldChange(
        field=body.change.field,
        from_val=_coerce_change_value(body.change.field, body.change.from_val),
        to_val=_coerce_change_value(body.change.field, body.change.to_val),
    )

    try:
        cf_result = counterfactual(rules, inputs, change)
    except (InvariantError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return CounterfactualResponse(
        result=_result_to_response(cf_result.new_result),
        delta=str(cf_result.delta),
        oop_delta=str(cf_result.oop_delta),
        changed_fields=cf_result.changed_fields,
        interaction_residual=str(cf_result.interaction_residual),
    )
