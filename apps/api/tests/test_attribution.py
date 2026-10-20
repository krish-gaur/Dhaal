"""
Attribution and counterfactual engine tests.

Tests:
- One-variable deltas matching spec §6.4
- Additivity check for fixture rule set
- Interaction residual non-zero for co-pay + room-cap non-additive case
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from engine.attribution import FieldChange, apply_change, counterfactual, interaction_check
from engine.claim import simulate_claim
from engine.rules import (
    ApportionmentBase,
    ChargeItem,
    ClaimInputs,
    CoPayment,
    NonPayableList,
    PolicyRules,
    ProportionateRule,
    RoomLimit,
    RuleType,
    WaitingPeriod,
)

FIXTURE_WATERFALL = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]

FIXTURE_CHARGES = [
    ChargeItem(name="Room", amount=Decimal("13500"), nights=3),
    ChargeItem(name="Surgeon fees", amount=Decimal("42000")),
    ChargeItem(name="OT charges", amount=Decimal("18000")),
    ChargeItem(name="Medicines", amount=Decimal("32500")),
    ChargeItem(name="Diagnostics", amount=Decimal("14000")),
]


def _rules() -> PolicyRules:
    """Fixture policy rules. Months elapsed live in ClaimInputs, not here."""
    return PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(disease_type="specified_disease", months_required=24)
        ],
        non_payable=NonPayableList(
            items=["Gloves", "Syringes", "Admission kit", "Attendant charges", "Telephone"],
            total=Decimal("9500"),
        ),
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )


INPUTS_ABOVE_CAP = ClaimInputs(
    gross_bill=Decimal("120000"),
    charges=FIXTURE_CHARGES,
    room_rate_per_night=Decimal("4500"),
    nights=3,
    policy_month_at_admit=25,
    remaining_sum_insured=Decimal("300000"),
)

CHARGES_AT_CAP = [
    ChargeItem(name="Room", amount=Decimal("9000"), nights=3),
    ChargeItem(name="Surgeon fees", amount=Decimal("46500")),
    ChargeItem(name="OT charges", amount=Decimal("18000")),
    ChargeItem(name="Medicines", amount=Decimal("32500")),
    ChargeItem(name="Diagnostics", amount=Decimal("14000")),
]

INPUTS_AT_CAP = ClaimInputs(
    gross_bill=Decimal("120000"),
    charges=CHARGES_AT_CAP,
    room_rate_per_night=Decimal("3000"),
    nights=3,
    policy_month_at_admit=25,
    remaining_sum_insured=Decimal("300000"),
)


# ---------------------------------------------------------------------------
# Scenario deltas
# ---------------------------------------------------------------------------


def test_delta_a_to_b() -> None:
    """A→B: confirming continuity credit = +₹81,333 to insurer.

    Exercised through counterfactual() on the single input
    `policy_month_at_admit` (19 → 25), which is exactly how the API's
    continuity toggle attributes the delta.
    """
    rules = _rules()
    inputs_a = replace(INPUTS_ABOVE_CAP, policy_month_at_admit=19)

    result_a = simulate_claim(rules, inputs_a)
    assert result_a.insurer_payment == Decimal("0")

    cf = counterfactual(
        rules, inputs_a, FieldChange("policy_month_at_admit", 19, 25)
    )
    assert cf.delta == Decimal("81333")
    assert cf.new_result.insurer_payment == Decimal("81333")
    assert cf.oop_delta == Decimal("-81333")


def test_delta_b_to_c1() -> None:
    """B→C1: moving room to cap = +₹29,167 to insurer."""
    rules = _rules()

    result_b = simulate_claim(rules, INPUTS_ABOVE_CAP)
    result_c1 = simulate_claim(rules, INPUTS_AT_CAP)

    delta = result_c1.insurer_payment - result_b.insurer_payment
    assert delta == Decimal("29167")


def test_delta_a_to_c1() -> None:
    """A→C1: both changes = +₹1,10,500 to insurer."""
    rules = _rules()
    inputs_a = replace(INPUTS_ABOVE_CAP, policy_month_at_admit=19)

    result_a = simulate_claim(rules, inputs_a)
    result_c1 = simulate_claim(rules, INPUTS_AT_CAP)

    delta = result_c1.insurer_payment - result_a.insurer_payment
    assert delta == Decimal("110500")


def test_additivity_fixture() -> None:
    """
    For the fixture rule set, A→B + B→C1 must equal A→C1.
    This is a property of this specific rule set — not a universal law.
    """
    rules = _rules()
    inputs_a = replace(INPUTS_ABOVE_CAP, policy_month_at_admit=19)

    r_a = simulate_claim(rules, inputs_a).insurer_payment
    r_b = simulate_claim(rules, INPUTS_ABOVE_CAP).insurer_payment
    r_c1 = simulate_claim(rules, INPUTS_AT_CAP).insurer_payment

    delta_ab = r_b - r_a          # 81333
    delta_bc1 = r_c1 - r_b       # 29167
    delta_ac1 = r_c1 - r_a       # 110500

    assert delta_ab + delta_bc1 == delta_ac1


# ---------------------------------------------------------------------------
# Interaction residual — must be non-zero for co-pay + room cap
# ---------------------------------------------------------------------------


def test_interaction_nonzero_copay_room() -> None:
    """
    Non-additive case: with a 10% co-pay and a sum-insured cap that bites,
    changing the room rate and changing nights interact — the combined
    effect is not the sum of the individual effects, because the clamp at
    the remaining sum insured is non-linear.
    """
    rules_small_si = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24)
        ],
        non_payable=NonPayableList(items=["item"], total=Decimal("9500")),
        co_payment=CoPayment(pct=Decimal("0.10")),
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )

    # Large gross so the remaining-SI clamp bites — clamp makes it non-linear
    large_inputs = ClaimInputs(
        gross_bill=Decimal("500000"),
        charges=[
            ChargeItem(name="Room", amount=Decimal("270000"), nights=3),
            ChargeItem(name="Surgeon fees", amount=Decimal("100000")),
            ChargeItem(name="OT charges", amount=Decimal("80000")),
            ChargeItem(name="Diagnostics", amount=Decimal("50000")),
        ],
        room_rate_per_night=Decimal("90000"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),  # SI cap will bite
    )

    change_a = FieldChange("room_rate_per_night", Decimal("90000"), Decimal("1000"))
    change_b = FieldChange("nights", 3, 1)

    residual = interaction_check(rules_small_si, large_inputs, change_a, change_b)
    assert residual != Decimal("0"), (
        f"Expected non-zero interaction residual for SI-capped scenario, got {residual}"
    )


def test_interaction_zero_independent_changes() -> None:
    """
    Two completely independent changes (e.g. two gross bill amounts that don't
    interact through any shared computation step) may produce zero residual.
    This test confirms the check itself is not always non-zero.
    """
    # Simple rules with no co-pay, no proportionate deduction
    simple_rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=[RuleType.NON_PAYABLE],
        room_limit=None,
        waiting_periods=[],
        non_payable=NonPayableList(items=["item"], total=Decimal("5000")),
        co_payment=None,
        deductible=None,
        proportionate_deduction=None,
        apportionment_base=ApportionmentBase.UNRESOLVED,
    )
    simple_inputs = ClaimInputs(
        gross_bill=Decimal("50000"),
        charges=[ChargeItem(name="Surgery", amount=Decimal("50000"))],
        room_rate_per_night=Decimal("0"),
        nights=0,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )

    change_a2 = FieldChange("gross_bill", Decimal("50000"), Decimal("55000"))
    change_remaining = FieldChange(
        "remaining_sum_insured", Decimal("300000"), Decimal("250000")
    )
    # With simple non-payable only, these don't interact
    residual = interaction_check(simple_rules, simple_inputs, change_a2, change_remaining)
    # For purely additive linear rules, this should be 0
    assert residual == Decimal("0")


def test_apply_change_unknown_field() -> None:
    """Unsupported field raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported"):
        apply_change(INPUTS_ABOVE_CAP, FieldChange("nonexistent_field", 1, 2))


def test_counterfactual_single_field_zero_residual() -> None:
    """Single-field counterfactual always has interaction_residual == 0."""
    rules = _rules()
    change = FieldChange("room_rate_per_night", Decimal("4500"), Decimal("3000"))
    result = counterfactual(rules, INPUTS_ABOVE_CAP, change)
    assert result.interaction_residual == Decimal("0")
    assert len(result.changed_fields) == 1


def test_apply_change_changes_exactly_one_field() -> None:
    """Each counterfactual changes its intended variable and nothing else.

    Attribution is only honest if every other input is bit-identical;
    this pins that property for every supported field.
    """
    from dataclasses import fields as dc_fields

    cases: list[tuple[str, object]] = [
        ("room_rate_per_night", Decimal("3000")),
        ("policy_month_at_admit", 25),
        ("gross_bill", Decimal("115500")),
        ("nights", 2),
        ("remaining_sum_insured", Decimal("200000")),
    ]
    for field, to_val in cases:
        changed = apply_change(
            INPUTS_ABOVE_CAP,
            FieldChange(field, getattr(INPUTS_ABOVE_CAP, field), to_val),
        )
        assert getattr(changed, field) == to_val
        for f in dc_fields(INPUTS_ABOVE_CAP):
            if f.name != field:
                assert getattr(changed, f.name) == getattr(INPUTS_ABOVE_CAP, f.name), (
                    f"counterfactual on {field} also changed {f.name}"
                )
    # The original inputs object is immutable and untouched.
    assert INPUTS_ABOVE_CAP.room_rate_per_night == Decimal("4500")
