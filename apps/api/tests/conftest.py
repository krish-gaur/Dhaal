"""
Shared pytest fixtures for the DHAAL engine test suite.

Fixture policy (as per spec §6.4):
  sum_insured = ₹3,00,000
  room cap = 1% / day = ₹3,000 / day
  3 nights
  24-month specified-disease waiting period
  non-payables = ₹9,500
  no co-pay, no deductible

Hospital bill (as per spec §6.4):
  room  = ₹13,500 (3 × ₹4,500)
  surgeon = ₹42,000
  OT = ₹18,000
  medicines = ₹32,500
  diagnostics = ₹14,000
  gross = ₹1,20,000
"""

from decimal import Decimal

import pytest

from engine.loans import AffordabilityContext
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

FIXTURE_WATERFALL = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]


@pytest.fixture
def fixture_charges() -> list[ChargeItem]:
    return [
        ChargeItem(name="Room", amount=Decimal("13500"), nights=3),
        ChargeItem(name="Surgeon fees", amount=Decimal("42000")),
        ChargeItem(name="OT charges", amount=Decimal("18000")),
        ChargeItem(name="Medicines", amount=Decimal("32500")),
        ChargeItem(name="Diagnostics", amount=Decimal("14000")),
    ]


@pytest.fixture
def fixture_rules_waiting_applies(fixture_charges: list[ChargeItem]) -> PolicyRules:
    """Fixture policy rules (waiting period 24 months).

    Kept under its original name: scenario A pairs these rules with
    inputs whose policy_month_at_admit=19 (months elapsed live in inputs).
    """
    return PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(
                disease_type="specified_disease",
                months_required=24,
            )
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


@pytest.fixture
def fixture_rules_continuity(fixture_charges: list[ChargeItem]) -> PolicyRules:
    """Same rules; scenarios B/C pair them with inputs at policy month 25."""
    return PolicyRules(
        sum_insured=Decimal("300000"),
        waterfall=FIXTURE_WATERFALL,
        room_limit=RoomLimit(basis="pct_sum_insured_per_day", value=Decimal("0.01")),
        waiting_periods=[
            WaitingPeriod(
                disease_type="specified_disease",
                months_required=24,
            )
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


@pytest.fixture
def fixture_inputs_above_cap(fixture_charges: list[ChargeItem]) -> ClaimInputs:
    """Scenario B: room ₹4,500/night (above ₹3,000 cap)."""
    return ClaimInputs(
        gross_bill=Decimal("120000"),
        charges=fixture_charges,
        room_rate_per_night=Decimal("4500"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )


@pytest.fixture
def fixture_inputs_at_cap(fixture_charges: list[ChargeItem]) -> ClaimInputs:
    """
    Scenario C1: room at cap (₹3,000/night), gross bill still ₹1,20,000.
    The ₹4,500 that was room is now moved to surgeon fees.
    """
    charges_at_cap = [
        ChargeItem(name="Room", amount=Decimal("9000"), nights=3),     # 3 × ₹3,000
        ChargeItem(name="Surgeon fees", amount=Decimal("46500")),       # +₹4,500
        ChargeItem(name="OT charges", amount=Decimal("18000")),
        ChargeItem(name="Medicines", amount=Decimal("32500")),
        ChargeItem(name="Diagnostics", amount=Decimal("14000")),
    ]
    return ClaimInputs(
        gross_bill=Decimal("120000"),
        charges=charges_at_cap,
        room_rate_per_night=Decimal("3000"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )


@pytest.fixture
def fixture_inputs_at_cap_reduced_bill() -> ClaimInputs:
    """Scenario C2: room at cap, bill reduced to ₹1,15,500."""
    charges = [
        ChargeItem(name="Room", amount=Decimal("9000"), nights=3),
        ChargeItem(name="Surgeon fees", amount=Decimal("42000")),
        ChargeItem(name="OT charges", amount=Decimal("18000")),
        ChargeItem(name="Medicines", amount=Decimal("28000")),
        ChargeItem(name="Diagnostics", amount=Decimal("18500")),
    ]
    return ClaimInputs(
        gross_bill=Decimal("115500"),
        charges=charges,
        room_rate_per_night=Decimal("3000"),
        nights=3,
        policy_month_at_admit=25,
        remaining_sum_insured=Decimal("300000"),
    )


@pytest.fixture
def fixture_affordability() -> AffordabilityContext:
    return AffordabilityContext(
        income_months=[
            Decimal("38000"), Decimal("31500"), Decimal("42000"), Decimal("27000"),
            Decimal("35500"), Decimal("24000"), Decimal("33000"), Decimal("29500"),
            Decimal("36000"), Decimal("22500"), Decimal("34000"), Decimal("30000"),
        ],
        essentials=Decimal("18500"),
        existing_emi=Decimal("4200"),
        savings=Decimal("35000"),
    )
