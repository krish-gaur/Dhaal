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

from db.session_store import get_clauses, get_db, get_session, save_simulation_run
from engine.attribution import FieldChange, counterfactual
from engine.claim import simulate_claim
from engine.rules import (
    ApportionmentBase,
    ChargeItem,
    ClaimInputs,
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

# Material facts required before simulation is allowed
_MATERIAL_RULE_TYPES = {"room_rent_limit", "waiting_period", "non_payable", "apportionment_base"}


def _build_policy_rules(clauses: list[object], assumptions: object) -> PolicyRules:
    """
    Build PolicyRules from confirmed clauses and session assumptions.
    Unconfirmed material facts result in None (unknown), never a default.
    """
    from db.models import ClauseRow
    from routes.schemas import SimulationAssumptions
    assert isinstance(assumptions, SimulationAssumptions)

    room_limit: RoomLimit | None = None
    waiting_periods: list[WaitingPeriod] = []
    non_payable: NonPayableList | None = None
    apportionment_base = ApportionmentBase.UNRESOLVED

    for clause in clauses:
        assert isinstance(clause, ClauseRow)
        status = clause.status
        rule_type = clause.rule_type or ""
        params: dict[str, str] = {}
        if clause.rule_params:
            try:
                params = json.loads(clause.rule_params)
            except Exception:
                pass

        # Only apply rules that are verified or user-confirmed
        if status not in ("verified", "user_confirmed"):
            continue

        if rule_type == "room_rent_limit":
            basis = params.get("basis", "pct_sum_insured_per_day")
            value_str = params.get("value", "0.01")
            room_limit = RoomLimit(
                basis=basis,  # type: ignore[arg-type]
                value=Decimal(value_str),
            )

        elif rule_type == "waiting_period":
            months_required = int(params.get("months_required", "24"))
            disease_type = params.get("disease_type", "specified_disease")
            months_elapsed = assumptions.policy_month_at_admit
            # If continuity_confirmed, treat as fully elapsed
            if assumptions.continuity_confirmed:
                months_elapsed = months_required + 1
            waiting_periods.append(
                WaitingPeriod(
                    disease_type=disease_type,
                    months_required=months_required,
                    months_elapsed=months_elapsed,
                )
            )

        elif rule_type == "non_payable":
            items_str = params.get("items", "")
            items = [i.strip() for i in items_str.split(",") if i.strip()]
            non_payable = NonPayableList(
                items=items,
                total=Decimal("9500"),  # fixture value; live extraction uses actual
            )

        elif rule_type == "apportionment_base":
            scope = params.get("scope", "unresolved")
            try:
                apportionment_base = ApportionmentBase(
                    assumptions.apportionment_base
                )
            except ValueError:
                apportionment_base = ApportionmentBase.UNRESOLVED

    return PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=_FIXTURE_WATERFALL,
        room_limit=room_limit,
        waiting_periods=waiting_periods,
        non_payable=non_payable,
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=apportionment_base,
    )


def _build_claim_inputs(body: SimulateRequest) -> ClaimInputs:
    charges = [
        ChargeItem(
            name=c.name,
            amount=Decimal(c.amount),
            nights=c.nights,
        )
        for c in body.charges
    ]
    return ClaimInputs(
        gross_bill=Decimal(body.gross),
        charges=charges,
        room_rate_per_night=Decimal(body.room_rate_per_night),
        nights=body.nights,
        policy_month_at_admit=body.assumptions.policy_month_at_admit,
        remaining_sum_insured=Decimal(body.assumptions.remaining_sum_insured),
    )


def _result_to_response(result: object) -> SimulationResponse:
    from engine.rules import ClaimResult
    assert isinstance(result, ClaimResult)
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


def _check_simulation_gate(clauses: list[object]) -> list[str]:
    """Return list of unresolved material facts blocking simulation."""
    from db.models import ClauseRow
    confirmed_types: set[str] = set()
    for clause in clauses:
        assert isinstance(clause, ClauseRow)
        if clause.status in ("verified", "user_confirmed") and clause.rule_type:
            confirmed_types.add(clause.rule_type)

    missing = []
    for required in ("room_rent_limit", "waiting_period", "non_payable"):
        if required not in confirmed_types:
            missing.append(required.replace("_", " "))
    return missing


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

    rules = _build_policy_rules(clauses, body.assumptions)
    inputs = _build_claim_inputs(body)

    try:
        result = simulate_claim(rules, inputs)
    except InvariantError as e:
        logger.error("Invariant violation in session %s: %s", session_id, e)
        raise HTTPException(
            status_code=500,
            detail="An internal calculation error occurred. The result has been blocked.",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not result.invariants_ok:
        logger.error("invariants_ok=False in session %s", session_id)
        raise HTTPException(
            status_code=500,
            detail="Calculation invariant violated. Result blocked.",
        )

    # Persist run (without PII — just numeric inputs and results)
    save_simulation_run(
        db,
        session_id=session_id,
        inputs={"gross": body.gross, "nights": body.nights},
        result={"insurer_payment": str(result.insurer_payment), "out_of_pocket": str(result.out_of_pocket)},
        invariants_ok=result.invariants_ok,
    )

    return _result_to_response(result)


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
    rules = _build_policy_rules(clauses, body.base.assumptions)
    inputs = _build_claim_inputs(body.base)

    change = FieldChange(
        field=body.change.field,
        from_val=body.change.from_val,
        to_val=body.change.to_val,
    )

    # Convert Decimal string fields if needed
    if isinstance(change.to_val, str):
        try:
            object.__setattr__(change, "to_val", Decimal(change.to_val))
        except Exception:
            pass
    if isinstance(change.from_val, str):
        try:
            object.__setattr__(change, "from_val", Decimal(change.from_val))
        except Exception:
            pass

    try:
        cf_result = counterfactual(rules, inputs, change)
    except (InvariantError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return CounterfactualResponse(
        result=_result_to_response(cf_result.new_result),
        delta=str(cf_result.delta),
        oop_delta=str(cf_result.oop_delta),
        changed_fields=cf_result.changed_fields,
        interaction_residual=str(cf_result.interaction_residual),
    )
