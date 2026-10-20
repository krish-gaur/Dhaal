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
    EXCLUSION = "exclusion"


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
    # Evidence trail: where this rule came from. The API layer fills these
    # from the source clause (page + clause id) so every deduction the
    # engine emits can be traced to its clause. Empty means "not
    # recorded" — the engine says so rather than inventing a page.
    citation: str = ""
    source_clause_id: str | None = None


@dataclass(frozen=True)
class WaitingPeriod:
    """
    A policy rule: coverage starts only after a waiting period elapses.

    Elapsed time is NOT part of the rule — it is a property of the claim
    event (`ClaimInputs.policy_month_at_admit` / `days_since_inception`,
    which already include any portability/continuity credit the caller
    has evidence for). Keeping elapsed in exactly one place (the inputs)
    is what makes the continuity counterfactual well-defined.

    Scopes:
    - "initial": day-based (use days_required, months_required=0);
      typically has an accident exception.
    - "specified": month-based; applies only to the diseases/procedures
      in `conditions` (condition tags). conditions=None means the clause
      as extracted does not enumerate conditions, so it applies to any
      condition — the caller is responsible for only constructing that
      form when the wording really is unconditional.
    - "pre_existing": month-based; applies only when the claim's
      condition is flagged pre-existing.

    `pending` marks a clause that exists but is not confirmed
    (user marked it unknown / unverified): the engine never applies it,
    but surfaces it as unresolved so the range reflects that it *might*.
    """

    disease_type: str
    months_required: int
    scope: Literal["initial", "specified", "pre_existing"] = "specified"
    conditions: tuple[str, ...] | None = None
    days_required: int | None = None
    accident_exception: bool = False
    pending: bool = False
    citation: str = ""
    source_clause_id: str | None = None


@dataclass(frozen=True)
class ExclusionRule:
    """
    A coverage exclusion: claims whose condition tag matches one of
    `conditions` are not covered at all. Distinct from a deduction —
    the engine reports it as an exclusion, never as a reduction.
    """

    conditions: tuple[str, ...]
    label: str = ""
    pending: bool = False
    citation: str = ""
    source_clause_id: str | None = None


@dataclass(frozen=True)
class NonPayableList:
    items: list[str]
    total: Decimal
    citation: str = ""
    source_clause_id: str | None = None


@dataclass(frozen=True)
class CoPayment:
    pct: Decimal  # e.g. Decimal("0.10") for 10%
    citation: str = ""
    source_clause_id: str | None = None


@dataclass(frozen=True)
class ProportionateRule:
    trigger: Literal["room_above_cap"]
    citation: str = ""
    source_clause_id: str | None = None


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
    # Coverage exclusions (condition-tagged). Evaluated by the EXCLUSION
    # waterfall step; empty when the policy has none extracted.
    exclusions: tuple[ExclusionRule, ...] = ()
    # Evidence trail for the deductible (a bare Decimal above).
    deductible_citation: str = ""
    deductible_clause_id: str | None = None


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
    # What the admission is for, as a condition tag matched against
    # waiting-period and exclusion clause condition lists. None means
    # "not supplied" — conditional rules then surface as unresolved
    # instead of being silently applied or silently skipped.
    condition_tag: str | None = None
    # True/False when known; None when not supplied.
    is_pre_existing: bool | None = None
    is_accident: bool = False
    # Days from first policy inception to admission, including any
    # credited continuity. Needed to evaluate day-based (initial)
    # waiting periods; None → such rules surface as unresolved.
    days_since_inception: int | None = None


@dataclass(frozen=True)
class Deduction:
    name: str
    amount: Decimal
    # Human-readable calculation basis, e.g. "₹74,000 × (1 − 0.6667)"
    basis: str
    rule_id: str
    citation: str
    # The clause this deduction traces to (None only when rules were
    # constructed without clause linkage, e.g. engine unit tests; the
    # API layer always sets it — no deduction without a source clause).
    source_clause_id: str | None = None


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
    RuleType.EXCLUSION,
    RuleType.WAITING_PERIOD,
    RuleType.NON_PAYABLE,
    RuleType.ROOM_RENT_LIMIT,
    RuleType.PROPORTIONATE_DEDUCTION,
    RuleType.CO_PAYMENT,
    RuleType.DEDUCTIBLE,
]
