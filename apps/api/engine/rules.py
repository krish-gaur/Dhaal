"""
Typed domain objects for the DHAAL financial engine.

Design rules enforced here:
- All monetary values are Decimal. float is never used for money.
- room_limit: RoomLimit | None means UNKNOWN, never "unlimited".
  None is unrepresentable as a numeric value — the type system enforces this.
- apportionment_base is always explicit. UNRESOLVED widens the result to a range.
- InvariantError is raised on conservation failure; it is never swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Literal


class RuleType(StrEnum):
    NON_PAYABLE = "non_payable"
    ROOM_RENT_LIMIT = "room_rent_limit"
    PROPORTIONATE_DEDUCTION = "proportionate_deduction"
    CO_PAYMENT = "co_payment"
    DEDUCTIBLE = "deductible"
    WAITING_PERIOD = "waiting_period"


class ApportionmentBase(StrEnum):
    """
    Which charges are subject to proportionate deduction.

    This is always an explicit, surfaced value — never a silent default.
    Moving between SURGEON_OT_DIAG and ALL_MEDICAL_EXPENSES changes the
    out-of-pocket by ₹24,667 in the fixture scenario.
    UNRESOLVED means the policy wording is ambiguous; the engine returns a range.
    """

    ROOM_RELATED_ONLY = "room_related_only"
    ALL_MEDICAL_EXPENSES = "all_medical_expenses"
    SURGEON_OT_DIAGNOSTICS = "surgeon_ot_diagnostics"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RoomLimit:
    basis: Literal["pct_sum_insured_per_day", "fixed_per_day"]
    value: Decimal  # 0.01 for 1%; or a fixed rupee amount per day


@dataclass(frozen=True)
class WaitingPeriod:
    """
    A policy rule: `months_required` months must elapse before this
    disease/procedure is covered.

    Months actually elapsed is NOT part of the rule — it is a property of
    the claim event, carried by `ClaimInputs.policy_month_at_admit`.
    Keeping elapsed in exactly one place (the inputs) is what makes the
    continuity counterfactual (change one input, recompute) well-defined.
    """

    disease_type: str
    months_required: int


@dataclass(frozen=True)
class NonPayableList:
    items: list[str]
    total: Decimal


@dataclass(frozen=True)
class CoPayment:
    pct: Decimal  # e.g. Decimal("0.10") for 10%


@dataclass(frozen=True)
class ProportionateRule:
    trigger: Literal["room_above_cap"]


@dataclass(frozen=True)
class PolicyRules:
    sum_insured: Decimal
    # Ordered list governing computation sequence; engine iterates this.
    waterfall: list[RuleType]
    # None == UNKNOWN, never "unlimited". Make this explicit.
    room_limit: RoomLimit | None
    waiting_periods: list[WaitingPeriod]
    non_payable: NonPayableList | None
    co_payment: CoPayment | None
    deductible: Decimal | None
    proportionate_deduction: ProportionateRule | None
    # MUST be explicit — drives ₹24,667 swing in fixture
    apportionment_base: ApportionmentBase
    # Interpretations of "associated medical expenses" that the extracted
    # policy wording can support. Only used to bound the out-of-pocket
    # range when apportionment_base is UNRESOLVED: the range must never
    # include a reading the wording expressly rules out (e.g. a clause
    # stating "Medicines … are not subject to proportionate deduction"
    # must not admit ALL_MEDICAL_EXPENSES as the worst case). Derived
    # from clause evidence at the API layer; the default (all concrete
    # bases) is the honest fallback when the wording's support is
    # itself unknown.
    apportionment_candidates: tuple[ApportionmentBase, ...] = (
        ApportionmentBase.ROOM_RELATED_ONLY,
        ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
        ApportionmentBase.ALL_MEDICAL_EXPENSES,
    )


@dataclass(frozen=True)
class ChargeItem:
    name: str
    amount: Decimal
    nights: int | None = None  # set for room charges


@dataclass(frozen=True)
class ClaimInputs:
    gross_bill: Decimal
    charges: list[ChargeItem]
    room_rate_per_night: Decimal
    nights: int
    policy_month_at_admit: int
    remaining_sum_insured: Decimal


@dataclass(frozen=True)
class Deduction:
    name: str
    amount: Decimal
    # Human-readable calculation basis, e.g. "₹74,000 × (1 − 0.6667)"
    basis: str
    rule_id: str
    citation: str


@dataclass(frozen=True)
class UnresolvedRule:
    rule_type: RuleType
    reason: str
    low_impact: Decimal   # best-case deduction (zero impact)
    high_impact: Decimal  # worst-case deduction


@dataclass(frozen=True)
class ClaimResult:
    gross_bill: Decimal
    non_payable_total: Decimal
    admissible: Decimal
    deductions: list[Deduction]
    insurer_payment: Decimal
    out_of_pocket: Decimal
    remaining_sum_insured: Decimal
    unresolved: list[UnresolvedRule]
    range_low: Decimal | None
    range_high: Decimal | None
    # Always present. If False the API blocks the result — never rendered.
    invariants_ok: bool


class InvariantError(Exception):
    """
    Raised when insurer_payment + out_of_pocket != gross_bill.
    This is never caught silently. The route layer converts it to a 500.
    """


# ---------------------------------------------------------------------------
# Default fixture waterfall — the order mandated by the fictional policy.
# Real policies may differ; always use PolicyRules.waterfall, not this.
# ---------------------------------------------------------------------------
FIXTURE_WATERFALL: list[RuleType] = [
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]
