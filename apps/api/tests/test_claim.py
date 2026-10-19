"""
Claim engine tests — golden values, intermediate values, invariants, edge cases.

Every golden value from spec §6.4 is asserted to the rupee.
Conservation (insurer + oop == gross) is checked on every scenario.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

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

FIXTURE_WATERFALL = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]


def _check_conservation(result: object) -> None:
    """Assert insurer + oop == gross for any ClaimResult."""
    from engine.rules import ClaimResult
    assert isinstance(result, ClaimResult)
    assert result.insurer_payment + result.out_of_pocket == result.gross_bill, (
        f"Conservation violated: {result.insurer_payment} + {result.out_of_pocket} "
        f"!= {result.gross_bill}"
    )


# ---------------------------------------------------------------------------
# Scenario A: waiting period applies (month 19 < 24 required)
# ---------------------------------------------------------------------------


def test_scenario_a_insurer_zero(
    fixture_rules_waiting_applies: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    """Waiting period not met → insurer pays nothing."""
    inputs = replace(fixture_inputs_above_cap, policy_month_at_admit=19)
    result = simulate_claim(fixture_rules_waiting_applies, inputs)
    assert result.insurer_payment == Decimal("0")
    assert result.out_of_pocket == Decimal("120000")
    assert result.invariants_ok is True
    _check_conservation(result)


def test_scenario_a_conservation(
    fixture_rules_waiting_applies: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    inputs = replace(fixture_inputs_above_cap, policy_month_at_admit=19)
    result = simulate_claim(fixture_rules_waiting_applies, inputs)
    _check_conservation(result)


# ---------------------------------------------------------------------------
# Scenario B: continuity confirmed, room above cap
# Golden: insurer = 81333, oop = 38667
# ---------------------------------------------------------------------------


def test_scenario_b_insurer_payment(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    assert result.insurer_payment == Decimal("81333")
    assert result.out_of_pocket == Decimal("38667")
    assert result.invariants_ok is True
    _check_conservation(result)


def test_scenario_b_non_payable(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    assert result.non_payable_total == Decimal("9500")


def test_scenario_b_admissible(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    # admissible_0 = 120000 - 9500 = 110500
    assert result.admissible == Decimal("110500")


def test_scenario_b_room_deduction(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    room_ded = next(d for d in result.deductions if d.rule_id == "room_rent_limit")
    # room_eligible = 3000 * 3 = 9000; room_billed = 4500 * 3 = 13500
    # room_deduction = 13500 - 9000 = 4500
    assert room_ded.amount == Decimal("4500")


def test_scenario_b_proportionate_deduction(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    prop_ded = next(d for d in result.deductions if d.rule_id == "proportionate_deduction")
    # ratio = 9000 / 13500 = 0.666666...
    # base = surgeon 42000 + OT 18000 + diagnostics 14000 = 74000
    # prop_deduction = 74000 * (1 - 0.666666...) = 74000 * 0.333333... = 24666.666...
    # assert to paisa level that it's between 24666 and 24667
    assert Decimal("24666") < prop_ded.amount < Decimal("24667")


def test_scenario_b_net_admissible(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_above_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_above_cap)
    # net = 120000 - 9500 - 4500 - 24666.666... = 81333.333...
    # insurer = floor(81333.333...) = 81333
    assert result.insurer_payment == Decimal("81333")


# ---------------------------------------------------------------------------
# Scenario C1: continuity confirmed, room at cap, bill ₹1,20,000
# Golden: insurer = 110500, oop = 9500
# ---------------------------------------------------------------------------


def test_scenario_c1(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_at_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_at_cap)
    assert result.insurer_payment == Decimal("110500")
    assert result.out_of_pocket == Decimal("9500")
    assert result.invariants_ok is True
    _check_conservation(result)


def test_scenario_c1_no_room_deduction(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_at_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_at_cap)
    room_deds = [d for d in result.deductions if d.rule_id == "room_rent_limit"]
    # Room is exactly at cap — no room deduction
    assert all(d.amount == Decimal("0") for d in room_deds) or len(room_deds) == 0


def test_scenario_c1_no_prop_deduction(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_at_cap: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_at_cap)
    prop_deds = [d for d in result.deductions if d.rule_id == "proportionate_deduction"]
    # Room at cap → no proportionate deduction
    assert len(prop_deds) == 0


# ---------------------------------------------------------------------------
# Scenario C2: continuity confirmed, room at cap, bill ₹1,15,500
# Golden: insurer = 106000, oop = 9500
# ---------------------------------------------------------------------------


def test_scenario_c2(
    fixture_rules_continuity: PolicyRules,
    fixture_inputs_at_cap_reduced_bill: ClaimInputs,
) -> None:
    result = simulate_claim(fixture_rules_continuity, fixture_inputs_at_cap_reduced_bill)
    assert result.insurer_payment == Decimal("106000")
    assert result.out_of_pocket == Decimal("9500")
    assert result.invariants_ok is True
    _check_conservation(result)


# ---------------------------------------------------------------------------
# Co-payment test (not in fixture, but must be implemented)
# ---------------------------------------------------------------------------


def test_copay_applied(fixture_inputs_above_cap: ClaimInputs) -> None:
    """10% co-pay applied after all other deductions; conservation holds."""
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=NonPayableList(items=["item"], total=Decimal("9500")),
        co_payment=CoPayment(pct=Decimal("0.10")),
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    result = simulate_claim(rules, fixture_inputs_above_cap)
    assert result.invariants_ok is True
    _check_conservation(result)
    # With copay the insurer pays less than scenario B
    assert result.insurer_payment < Decimal("81333")
    # Conservation must still hold
    assert result.insurer_payment + result.out_of_pocket == Decimal("120000")


def test_deductible_applied(fixture_inputs_above_cap: ClaimInputs) -> None:
    """₹10,000 deductible; conservation holds."""
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=NonPayableList(items=["item"], total=Decimal("9500")),
        co_payment=None,
        deductible=Decimal("10000"),
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    result = simulate_claim(rules, fixture_inputs_above_cap)
    assert result.invariants_ok is True
    _check_conservation(result)
    ded = next(d for d in result.deductions if d.rule_id == "deductible")
    assert ded.amount == Decimal("10000")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_gross_zero(fixture_rules_continuity: PolicyRules) -> None:
    inputs = ClaimInputs(
        gross_bill=Decimal("0"),
        charges=[],
        room_rate_per_night=Decimal("0"),
        nights=0,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )
    result = simulate_claim(fixture_rules_continuity, inputs)
    assert result.insurer_payment == Decimal("0")
    assert result.out_of_pocket == Decimal("0")
    _check_conservation(result)


def test_gross_five_crore(fixture_rules_continuity: PolicyRules) -> None:
    """Very large bill — insurer capped at sum insured; conservation holds."""
    charges = [ChargeItem(name="Surgery", amount=Decimal("5000000"))]
    inputs = ClaimInputs(
        gross_bill=Decimal("5000000"),
        charges=charges,
        room_rate_per_night=Decimal("4500"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )
    result = simulate_claim(fixture_rules_continuity, inputs)
    assert result.insurer_payment <= Decimal("300000")
    _check_conservation(result)
    assert result.invariants_ok is True


def test_room_limit_none_returns_unresolved(fixture_inputs_above_cap: ClaimInputs) -> None:
    """room_limit=None must produce an unresolved entry, never a numeric deduction."""
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=None,  # UNKNOWN
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=NonPayableList(items=["item"], total=Decimal("9500")),
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    result = simulate_claim(rules, fixture_inputs_above_cap)
    # Must have an unresolved entry
    unresolved_types = [u.rule_type.value for u in result.unresolved]
    assert "room_rent_limit" in unresolved_types
    # Must NOT have a room_rent_limit deduction (no default assumption)
    room_deds = [d for d in result.deductions if d.rule_id == "room_rent_limit"]
    assert len(room_deds) == 0
    _check_conservation(result)


def test_negative_gross_raises() -> None:
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=None,
        waiting_periods=[],
        non_payable=None,
        co_payment=None,
        deductible=None,
        proportionate_deduction=None,
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    inputs = ClaimInputs(
        gross_bill=Decimal("-1"),
        charges=[],
        room_rate_per_night=Decimal("0"),
        nights=0,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )
    with pytest.raises(ValueError):
        simulate_claim(rules, inputs)


def test_rounding_once_floor() -> None:
    """
    insurer_payment is ROUND_FLOOR exactly once.
    Verify the floor is applied: net_admissible = 81333.333... → insurer = 81333.
    """
    from engine.rules import FIXTURE_WATERFALL as _wf
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=_wf,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=NonPayableList(items=["item"], total=Decimal("9500")),
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    charges = [
        ChargeItem(name="Room", amount=Decimal("13500"), nights=3),
        ChargeItem(name="Surgeon fees", amount=Decimal("42000")),
        ChargeItem(name="OT charges", amount=Decimal("18000")),
        ChargeItem(name="Medicines", amount=Decimal("32500")),
        ChargeItem(name="Diagnostics", amount=Decimal("14000")),
    ]
    inputs = ClaimInputs(
        gross_bill=Decimal("120000"),
        charges=charges,
        room_rate_per_night=Decimal("4500"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )
    result = simulate_claim(rules, inputs)
    # Must be exactly 81333, not 81334 (ROUND_FLOOR not ROUND_HALF_UP)
    assert result.insurer_payment == Decimal("81333")
    # And conservation holds
    assert result.insurer_payment + result.out_of_pocket == Decimal("120000")
