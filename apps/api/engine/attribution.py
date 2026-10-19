"""
Counterfactual and interaction detection for the claim engine.

Design rules:
- A counterfactual changes exactly ONE input variable.
- The API layer enforces single-field changes; if two fields change the UI
  shows a message and does not call this endpoint.
- interaction_check computes the non-additivity residual:
    residual = f(a+b) - f(a) - f(b) + f(base)
  Zero means the changes are purely additive for this rule set.
  Non-zero means they interact and cannot be independently attributed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from engine.claim import simulate_claim
from engine.rules import ClaimInputs, ClaimResult, PolicyRules

_ZERO = Decimal("0")


@dataclass(frozen=True)
class FieldChange:
    field: str
    from_val: Any
    to_val: Any


@dataclass(frozen=True)
class CounterfactualResult:
    base_result: ClaimResult
    new_result: ClaimResult
    delta: Decimal           # new insurer_payment - base insurer_payment (positive = more covered)
    oop_delta: Decimal       # new oop - base oop (negative = better for user)
    changed_fields: list[str]
    interaction_residual: Decimal  # zero for single-field changes


# Supported fields for counterfactual changes
_SUPPORTED_FIELDS = {
    "room_rate_per_night",
    "policy_month_at_admit",
    "gross_bill",
    "nights",
    "remaining_sum_insured",
}


def apply_change(inputs: ClaimInputs, change: FieldChange) -> ClaimInputs:
    """
    Return a new ClaimInputs with one field changed.
    Uses dataclass replace — the original is immutable.
    """
    if change.field not in _SUPPORTED_FIELDS:
        raise ValueError(
            f"Unsupported counterfactual field: '{change.field}'. "
            f"Supported: {sorted(_SUPPORTED_FIELDS)}"
        )
    kwargs: dict[str, Any] = {change.field: change.to_val}
    return replace(inputs, **kwargs)


def counterfactual(
    rules: PolicyRules,
    inputs: ClaimInputs,
    change: FieldChange,
) -> CounterfactualResult:
    """
    Compute a single-variable counterfactual.

    Only one field changes. The interaction_residual is always zero for
    single-field counterfactuals (by definition — it requires two changes).
    """
    base_result = simulate_claim(rules, inputs)
    new_inputs = apply_change(inputs, change)
    new_result = simulate_claim(rules, new_inputs)

    delta = new_result.insurer_payment - base_result.insurer_payment
    oop_delta = new_result.out_of_pocket - base_result.out_of_pocket

    return CounterfactualResult(
        base_result=base_result,
        new_result=new_result,
        delta=delta,
        oop_delta=oop_delta,
        changed_fields=[change.field],
        interaction_residual=_ZERO,
    )


def interaction_check(
    rules: PolicyRules,
    inputs: ClaimInputs,
    change_a: FieldChange,
    change_b: FieldChange,
) -> Decimal:
    """
    Test whether two changes are additive or interact.

    Computes:
        additive_delta = (f(a) - f(base)) + (f(b) - f(base))
        actual_delta   = f(a+b) - f(base)
        residual       = actual_delta - additive_delta

    Returns the residual (Decimal).
    - Zero means the changes are purely additive.
    - Non-zero means they interact; do not attribute independently.

    Example of non-additive case: co-pay + room-cap deduction applied in
    sequence. The co-pay is a percentage of the net-after-room, so changing
    the room cap changes the co-pay base, making the combined effect
    non-additive.
    """
    r_base = simulate_claim(rules, inputs).insurer_payment
    r_a = simulate_claim(rules, apply_change(inputs, change_a)).insurer_payment
    r_b = simulate_claim(rules, apply_change(inputs, change_b)).insurer_payment
    r_ab = simulate_claim(
        rules,
        apply_change(apply_change(inputs, change_a), change_b),
    ).insurer_payment

    additive = (r_a - r_base) + (r_b - r_base)
    actual = r_ab - r_base
    return actual - additive
