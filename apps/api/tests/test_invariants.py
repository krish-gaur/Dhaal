"""
Property-based invariant tests using Hypothesis.

Tests:
- Conservation: insurer + oop == gross for 10,000 random inputs
- Monotonicity: higher admissible charge cannot reduce insurer_payment
- Monotonicity: higher room cap cannot increase out_of_pocket
- Missing rule → unknown returned, never a numeric default
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from engine.claim import simulate_claim
from engine.rules import (
    ApportionmentBase,
    ChargeItem,
    ClaimInputs,
    NonPayableList,
    PolicyRules,
    ProportionateRule,
    RoomLimit,
    RuleType,
    WaitingPeriod,
)

WATERFALL = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]


def _rules(
    room_cap_pct: Decimal = Decimal("0.01"),
    non_payable_total: Decimal = Decimal("0"),
    room_limit: RoomLimit | None = None,
) -> PolicyRules:
    rl = room_limit or RoomLimit(basis="pct_sum_insured_per_day", value=room_cap_pct)
    return PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=WATERFALL,
        room_limit=rl,
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=NonPayableList(
            items=["item"], total=non_payable_total
        ) if non_payable_total > Decimal("0") else None,
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )


def _inputs(
    gross: Decimal,
    room_rate: Decimal,
    nights: int = 3,
) -> ClaimInputs:
    # Build a simple bill where surgeon+OT+diag sum to gross - room
    room_total = room_rate * nights
    other = max(Decimal("0"), gross - room_total)
    surgeon = other * Decimal("0.57")   # ~57% of non-room
    ot = other * Decimal("0.24")
    diag = other - surgeon - ot

    charges = [
        ChargeItem(name="Room", amount=room_total, nights=nights),
        ChargeItem(name="Surgeon fees", amount=surgeon),
        ChargeItem(name="OT charges", amount=ot),
        ChargeItem(name="Diagnostics", amount=diag),
    ]
    return ClaimInputs(
        gross_bill=gross,
        charges=charges,
        room_rate_per_night=room_rate,
        nights=nights,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )


# ---------------------------------------------------------------------------
# Conservation: insurer + oop == gross over 10,000 random inputs
# ---------------------------------------------------------------------------


@given(
    gross=st.decimals(min_value=Decimal("1000"), max_value=Decimal("1000000"),
                      allow_nan=False, allow_infinity=False, places=0),
    room_rate=st.decimals(min_value=Decimal("1000"), max_value=Decimal("15000"),
                          allow_nan=False, allow_infinity=False, places=0),
    non_payable_frac=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"),
                                 allow_nan=False, allow_infinity=False, places=4),
    cap_pct=st.decimals(min_value=Decimal("0.005"), max_value=Decimal("0.03"),
                        allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=10000, suppress_health_check=[HealthCheck.too_slow])
def test_conservation_property(
    gross: Decimal,
    room_rate: Decimal,
    non_payable_frac: Decimal,
    cap_pct: Decimal,
) -> None:
    non_payable = (gross * non_payable_frac).to_integral_value()
    # Clamp non_payable to not exceed gross
    non_payable = min(non_payable, gross)
    rules = _rules(
        room_cap_pct=cap_pct,
        non_payable_total=non_payable,
    )
    inputs = _inputs(gross=gross, room_rate=room_rate)
    result = simulate_claim(rules, inputs)
    assert result.insurer_payment + result.out_of_pocket == result.gross_bill, (
        f"Conservation failed: {result.insurer_payment} + {result.out_of_pocket} "
        f"!= {result.gross_bill}"
    )
    assert result.insurer_payment >= Decimal("0")
    assert result.out_of_pocket >= Decimal("0")


# ---------------------------------------------------------------------------
# Monotonicity: raising an admissible charge cannot reduce insurer_payment
# ---------------------------------------------------------------------------


@given(
    surgeon_base=st.decimals(min_value=Decimal("10000"), max_value=Decimal("80000"),
                             allow_nan=False, allow_infinity=False, places=0),
    increment=st.decimals(min_value=Decimal("1"), max_value=Decimal("5000"),
                          allow_nan=False, allow_infinity=False, places=0),
)
@settings(max_examples=500)
def test_monotonicity_higher_charge(
    surgeon_base: Decimal,
    increment: Decimal,
) -> None:
    """Increasing an admissible charge (not a non-payable) by ₹1 or more
    cannot reduce insurer_payment."""
    rules = _rules(room_cap_pct=Decimal("0.01"))

    def make_inputs(surgeon: Decimal) -> ClaimInputs:
        room = Decimal("13500")
        gross = room + surgeon + Decimal("18000") + Decimal("32500") + Decimal("14000")
        charges = [
            ChargeItem(name="Room", amount=room, nights=3),
            ChargeItem(name="Surgeon fees", amount=surgeon),
            ChargeItem(name="OT charges", amount=Decimal("18000")),
            ChargeItem(name="Medicines", amount=Decimal("32500")),
            ChargeItem(name="Diagnostics", amount=Decimal("14000")),
        ]
        return ClaimInputs(
            gross_bill=gross,
            charges=charges,
            room_rate_per_night=Decimal("4500"),
            nights=3,
            policy_month_at_admit=25,
            remaining_sum_insured=Decimal("300000"),
        )

    r_base = simulate_claim(rules, make_inputs(surgeon_base))
    r_high = simulate_claim(rules, make_inputs(surgeon_base + increment))

    # Higher admissible charge → gross is higher → insurer can only stay same or increase
    # (subject to sum-insured cap)
    assert r_high.insurer_payment >= r_base.insurer_payment, (
        f"Monotonicity violated: base insurer={r_base.insurer_payment}, "
        f"higher insurer={r_high.insurer_payment}"
    )


# ---------------------------------------------------------------------------
# Monotonicity: higher room cap cannot increase out_of_pocket
# ---------------------------------------------------------------------------


@given(
    cap_low=st.decimals(min_value=Decimal("0.005"), max_value=Decimal("0.01"),
                        allow_nan=False, allow_infinity=False, places=4),
    cap_delta=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.02"),
                          allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=500)
def test_monotonicity_higher_room_cap(cap_low: Decimal, cap_delta: Decimal) -> None:
    """Higher room cap means less deduction → insurer pays same or more → OOP same or lower."""
    cap_high = cap_low + cap_delta

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

    r_low_cap = simulate_claim(_rules(room_cap_pct=cap_low), inputs)
    r_high_cap = simulate_claim(_rules(room_cap_pct=cap_high), inputs)

    assert r_high_cap.out_of_pocket <= r_low_cap.out_of_pocket, (
        f"Monotonicity violated: low_cap OOP={r_low_cap.out_of_pocket}, "
        f"high_cap OOP={r_high_cap.out_of_pocket}"
    )


# ---------------------------------------------------------------------------
# Missing rule → unknown, never numeric default
# ---------------------------------------------------------------------------


def test_missing_room_limit_unresolved_not_zero() -> None:
    """room_limit=None must produce unresolved entry, not a deduction of zero."""
    rules = PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=WATERFALL,
        room_limit=None,  # UNKNOWN
        waiting_periods=[
            WaitingPeriod(disease_type="x", months_required=24, months_elapsed=25)
        ],
        non_payable=None,
        co_payment=None,
        deductible=None,
        proportionate_deduction=ProportionateRule(trigger="room_above_cap"),
        apportionment_base=ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
    )
    inputs = _inputs(Decimal("120000"), Decimal("4500"))
    result = simulate_claim(rules, inputs)

    # Must have an unresolved entry for room_rent_limit
    unresolved_types = {u.rule_type.value for u in result.unresolved}
    assert "room_rent_limit" in unresolved_types

    # Must NOT have a room deduction (no silent default)
    room_deds = [d for d in result.deductions if d.rule_id == "room_rent_limit"]
    assert len(room_deds) == 0

    # Conservation must still hold
    assert result.insurer_payment + result.out_of_pocket == result.gross_bill
