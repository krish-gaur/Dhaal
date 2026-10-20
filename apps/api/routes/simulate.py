"""
Simulation and counterfactual routes.

The engine is called here. The LLM is never called here.
If invariants_ok == False, the route returns 500 — the result is NEVER rendered.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date
from decimal import Decimal
from typing import Literal

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
    ExclusionRule,
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
    RuleType.EXCLUSION,
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


# When several clauses share a material type (e.g. three waiting
# periods), the fact's state is the WEAKEST clause state — one
# undecided clause must not be hidden by a verified sibling.
_STATUS_SEVERITY = {
    "conflicting": 0,
    "unverified": 1,
    "unknown": 2,
    "user_confirmed": 3,
    "verified": 4,
    "synthetic": 5,
}


def material_fact_states(clauses: list[ClauseRow]) -> dict[str, str]:
    """Weakest status per material rule type; 'missing' when none exists."""
    states = {t: "missing" for t in _MATERIAL_RULE_TYPES}
    for clause in clauses:
        rule_type = clause.rule_type or ""
        if rule_type not in states:
            continue
        current = states[rule_type]
        if current == "missing" or _STATUS_SEVERITY.get(
            clause.status, 1
        ) < _STATUS_SEVERITY.get(current, 1):
            states[rule_type] = clause.status
    return states


def _citation_for(clause: ClauseRow, params: dict[str, str]) -> str:
    """Human citation for a clause: its page and section, from the record."""
    parts: list[str] = []
    if clause.page is not None:
        parts.append(f"page {clause.page}")
    section = params.get("section", "").strip()
    if section:
        parts.append(f"§{section}")
    return ", ".join(parts)


def _parse_conditions(params: dict[str, str]) -> tuple[str, ...] | None:
    raw = params.get("conditions")
    if raw is None:
        return None
    tags = tuple(t.strip() for t in raw.split(",") if t.strip())
    return tags or None


def _build_policy_rules(
    clauses: list[ClauseRow], assumptions: SimulationAssumptions
) -> PolicyRules:
    """
    Build PolicyRules from session clauses and explicit assumptions.

    Honesty rules:
    - A deduction rule is applied only when its clause is verified or
      user-confirmed, and always carries that clause's citation and id —
      no policy-specific deduction exists without a source clause.
    - Coverage gates (waiting periods, exclusions) from unconfirmed
      clauses are included as *pending*: never applied, but surfaced by
      the engine as unresolved so the result range reflects them.
    - Two applied clauses that disagree on the same money parameter are
      a conflict requiring human review (ValueError → 422), never a
      silent last-one-wins.
    - Sum insured and the non-payable billed total come from the
      request's explicit assumptions, not constants in this file.
    - Months elapsed is a claim input (ClaimInputs), not part of a rule.
    """
    room_limit: RoomLimit | None = None
    room_limit_from: str | None = None
    waiting_periods: list[WaitingPeriod] = []
    exclusions: list[ExclusionRule] = []
    non_payable_items: list[str] = []
    non_payable_citation = ""
    non_payable_clause_id: str | None = None
    co_payment: CoPayment | None = None
    co_payment_from: str | None = None
    deductible: Decimal | None = None
    deductible_citation = ""
    deductible_clause_id: str | None = None
    deductible_from: str | None = None
    apportionment_base = ApportionmentBase.UNRESOLVED
    apportionment_scope_from: tuple[str, str] | None = None
    apportionment_citation = ""
    apportionment_clause_id: str | None = None
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
        citation = _citation_for(clause, params)

        if rule_type == "proportionate_deduction" and applied:
            has_proportionate = True
            if apportionment_clause_id is None:
                apportionment_citation, apportionment_clause_id = citation, clause.id

        if rule_type == "apportionment_base" and status in _DECIDED_STATUSES:
            # The existence of this clause (in any decided state) is the
            # evidence that a proportionate deduction rule applies.
            has_proportionate = True
            apportionment_citation, apportionment_clause_id = citation, clause.id
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
                ap_scope = params.get("scope", "unresolved")
                if ap_scope in _CONCRETE_BASES:
                    # A confirmed interpretation recorded on the clause wins.
                    if (
                        apportionment_scope_from is not None
                        and apportionment_scope_from[0] != ap_scope
                    ):
                        raise ValueError(
                            "Conflicting apportionment clauses "
                            f"({apportionment_scope_from[1]} vs {clause.id}) — "
                            "human review required"
                        )
                    apportionment_scope_from = (ap_scope, clause.id)
                    apportionment_base = ApportionmentBase(ap_scope)
                else:
                    # Clause confirmed but its own scope is unresolved: the
                    # interpretation is the user's explicit simulation choice.
                    apportionment_base = ApportionmentBase(
                        assumptions.apportionment_base
                    )

        # Coverage gates: included from any existing clause; unconfirmed
        # ones are pending (surfaced as unresolved, never applied).
        if rule_type == "waiting_period":
            days_raw = params.get("days_required")
            scope_raw = params.get("scope", "")
            scope: Literal["initial", "specified", "pre_existing"]
            if scope_raw == "initial":
                scope = "initial"
            elif scope_raw == "pre_existing":
                scope = "pre_existing"
            elif scope_raw == "specified":
                scope = "specified"
            elif days_raw:
                scope = "initial"
            elif "pre" in params.get("disease_type", ""):
                scope = "pre_existing"
            else:
                scope = "specified"
            waiting_periods.append(
                WaitingPeriod(
                    disease_type=params.get("disease_type", "specified_disease"),
                    months_required=int(params.get("months_required", "0")),
                    scope=scope,
                    conditions=_parse_conditions(params),
                    days_required=int(days_raw) if days_raw else None,
                    accident_exception=params.get("accident_exception") == "true",
                    pending=not applied,
                    citation=citation,
                    source_clause_id=clause.id,
                )
            )
            continue

        if rule_type == "exclusion":
            conditions = _parse_conditions(params)
            if conditions:
                exclusions.append(
                    ExclusionRule(
                        conditions=conditions,
                        label=params.get("label", ""),
                        pending=not applied,
                        citation=citation,
                        source_clause_id=clause.id,
                    )
                )
            continue

        if not applied:
            continue

        if rule_type == "room_rent_limit":
            basis = params.get("basis", "")
            if basis not in ("pct_sum_insured_per_day", "fixed_per_day"):
                raise ValueError(f"Unknown room limit basis: '{basis}'")
            new_limit = RoomLimit(
                basis=basis,  # type: ignore[arg-type]
                value=Decimal(params.get("value", "0")),
                citation=citation,
                source_clause_id=clause.id,
            )
            if room_limit is not None and (
                room_limit.basis != new_limit.basis
                or room_limit.value != new_limit.value
            ):
                raise ValueError(
                    f"Conflicting room-rent-limit clauses ({room_limit_from} "
                    f"vs {clause.id}) — human review required"
                )
            room_limit, room_limit_from = new_limit, clause.id

        elif rule_type == "non_payable":
            # Endorsements can extend the list: union across applied clauses.
            for raw_item in params.get("items", "").split(","):
                item = raw_item.strip()
                if item and item not in non_payable_items:
                    non_payable_items.append(item)
            if non_payable_clause_id is None:
                non_payable_citation, non_payable_clause_id = citation, clause.id

        elif rule_type == "co_payment":
            new_copay = CoPayment(
                pct=Decimal(params.get("pct", "0")),
                citation=citation,
                source_clause_id=clause.id,
            )
            if co_payment is not None and co_payment.pct != new_copay.pct:
                raise ValueError(
                    f"Conflicting co-payment clauses ({co_payment_from} vs "
                    f"{clause.id}) — human review required"
                )
            co_payment, co_payment_from = new_copay, clause.id

        elif rule_type == "deductible":
            amount = Decimal(params.get("amount", "0"))
            if deductible is not None and deductible != amount:
                raise ValueError(
                    f"Conflicting deductible clauses ({deductible_from} vs "
                    f"{clause.id}) — human review required"
                )
            deductible = amount
            deductible_citation, deductible_clause_id = citation, clause.id
            deductible_from = clause.id

    # The policy says WHICH items are non-payable; the billed total is an
    # explicit input. Without a total the deduction stays unknown (the
    # engine returns a range) — and without an applied non-payable clause
    # there is no source for the deduction, so none is applied.
    non_payable: NonPayableList | None = None
    if (
        non_payable_clause_id is not None
        and assumptions.non_payable_total is not None
    ):
        non_payable = NonPayableList(
            items=non_payable_items,
            total=Decimal(assumptions.non_payable_total),
            citation=non_payable_citation,
            source_clause_id=non_payable_clause_id,
        )

    return PolicyRules(
        sum_insured=Decimal(assumptions.sum_insured),
        waterfall=_FIXTURE_WATERFALL,
        room_limit=room_limit,
        waiting_periods=waiting_periods,
        non_payable=non_payable,
        co_payment=co_payment,
        deductible=deductible,
        proportionate_deduction=(
            ProportionateRule(
                trigger="room_above_cap",
                citation=apportionment_citation,
                source_clause_id=apportionment_clause_id,
            )
            if has_proportionate
            else None
        ),
        apportionment_base=apportionment_base,
        apportionment_candidates=apportionment_candidates,
        exclusions=tuple(exclusions),
        deductible_citation=deductible_citation,
        deductible_clause_id=deductible_clause_id,
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
    # Elapsed cover is derived, never assumed: when inception and
    # admission dates are supplied, whole calendar months and days are
    # computed from them, plus any evidenced continuity/portability
    # credit (months). Without dates we fall back to the explicit
    # policy_month_at_admit input; day-based (initial) waiting periods
    # then surface as unresolved because they cannot be evaluated.
    a = body.assumptions
    effective_month = a.policy_month_at_admit
    days_since_inception: int | None = None
    if a.inception_date and a.admission_date:
        inception = date.fromisoformat(a.inception_date)
        admission = date.fromisoformat(a.admission_date)
        if admission < inception:
            raise ValueError(
                "admission_date is before inception_date — check the dates"
            )
        months = (admission.year - inception.year) * 12 + (
            admission.month - inception.month
        )
        if admission.day < inception.day:
            months -= 1
        effective_month = months
        days_since_inception = (admission - inception).days
    effective_month += a.continuity_credit_months
    if days_since_inception is not None:
        # Credited months also count toward the initial (day-based) wait;
        # 30 days per credited month is the conservative conversion.
        days_since_inception += a.continuity_credit_months * 30
    # Legacy continuity flag: "treat the waiting period as served" —
    # raise the effective month to the largest month-based requirement.
    if a.continuity_confirmed:
        month_requirements = [
            wp.months_required
            for wp in rules.waiting_periods
            if wp.days_required is None
        ]
        if month_requirements:
            effective_month = max(effective_month, max(month_requirements))
    return ClaimInputs(
        gross_bill=Decimal(body.gross),
        charges=charges,
        room_rate_per_night=Decimal(body.room_rate_per_night),
        nights=body.nights,
        policy_month_at_admit=effective_month,
        remaining_sum_insured=Decimal(body.assumptions.remaining_sum_insured),
        condition_tag=a.condition_tag,
        is_pre_existing=a.is_pre_existing,
        is_accident=a.is_accident,
        days_since_inception=days_since_inception,
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
                source_clause_id=d.source_clause_id,
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
            "days_since_inception": inputs.days_since_inception,
            "condition_tag": inputs.condition_tag,
            "is_pre_existing": inputs.is_pre_existing,
            "inception_date": body.assumptions.inception_date,
            "admission_date": body.assumptions.admission_date,
            "continuity_credit_months": body.assumptions.continuity_credit_months,
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
