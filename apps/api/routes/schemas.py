"""
Pydantic v2 request/response schemas for the DHAAL API.

Design rules:
- Decimal values serialised as strings in all responses to avoid float precision loss.
- The frontend parses these strings for display only; it never does arithmetic.
- Every error response has: error (snake_case), message (user-readable), code (HTTP).
- No bare dict anywhere; every shape is a typed Pydantic model.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class ApiError(BaseModel):
    error: str       # machine-readable snake_case
    message: str     # user-readable, Grade-8 level
    code: int        # HTTP status code


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    goal: str | None = None
    use_fixture: bool = True


class SessionResponse(BaseModel):
    session_id: str
    mode: Literal["fixture", "live"]


class DeleteSessionResponse(BaseModel):
    deleted: bool
    verified: bool
    counts: dict[str, int]


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    mode: Literal["fixture", "live"]


# ---------------------------------------------------------------------------
# Clauses
# ---------------------------------------------------------------------------


class VerificationResponse(BaseModel):
    schema_valid: bool
    quote_found: bool
    numbers_supported: bool
    interpretation_status: str
    reason: str


class RuleParamResponse(BaseModel):
    type: str
    params: dict[str, str]


class ClauseResponse(BaseModel):
    clause_id: str
    document_id: str
    page: int | None
    char_start: int | None
    char_end: int | None
    quote: str | None
    quote_hash: str | None
    rule: RuleParamResponse
    verification: VerificationResponse


class PatchClauseRequest(BaseModel):
    status: Literal["user_confirmed", "unknown"]
    override: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def _validate_decimal_str(value: str) -> str:
    """Reject values that are not parseable Decimals at the API boundary."""
    try:
        Decimal(value)
    except Exception as exc:
        raise ValueError(f"'{value}' is not a valid decimal amount") from exc
    return value


class ChargeItemRequest(BaseModel):
    name: str
    amount: str   # Decimal as string
    nights: int | None = None

    _valid_amount = field_validator("amount")(_validate_decimal_str)


class SimulationAssumptions(BaseModel):
    policy_month_at_admit: int = Field(ge=0)
    remaining_sum_insured: str
    # Sum insured of the policy (drives %-of-SI room caps). Required and
    # explicit — never silently defaulted.
    sum_insured: str
    # Billed total of non-payable items in THIS bill. The policy lists which
    # items are non-payable; how much they cost comes from the hospital
    # estimate. None means "not known" → the engine returns a range.
    non_payable_total: str | None = None
    # Which charges the proportionate deduction applies to. Required and
    # explicit; "unresolved" is a legal value and widens the result to a range.
    apportionment_base: str
    # Legacy convenience: when true, the waiting period is treated as served.
    # The frontend normally sends the effective policy_month_at_admit instead.
    continuity_confirmed: bool = False

    _valid_decimals = field_validator(
        "remaining_sum_insured", "sum_insured"
    )(_validate_decimal_str)

    @field_validator("non_payable_total")
    @classmethod
    def _valid_non_payable_total(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_decimal_str(value)

    @field_validator("apportionment_base")
    @classmethod
    def _valid_apportionment_base(cls, value: str) -> str:
        allowed = {
            "room_related_only",
            "all_medical_expenses",
            "surgeon_ot_diagnostics",
            "unresolved",
        }
        if value not in allowed:
            raise ValueError(
                f"apportionment_base must be one of: {sorted(allowed)}"
            )
        return value


class SimulateRequest(BaseModel):
    gross: str
    charges: list[ChargeItemRequest]
    room_rate_per_night: str
    nights: int = Field(ge=1)
    assumptions: SimulationAssumptions

    _valid_decimals = field_validator("gross", "room_rate_per_night")(
        _validate_decimal_str
    )


class DeductionResponse(BaseModel):
    name: str
    amount: str   # Decimal as string
    basis: str
    rule_id: str
    citation: str


class UnresolvedRuleResponse(BaseModel):
    rule_type: str
    reason: str
    low_impact: str
    high_impact: str


class SimulationResponse(BaseModel):
    gross_bill: str
    non_payable_total: str
    admissible: str
    deductions: list[DeductionResponse]
    insurer_payment: str
    out_of_pocket: str
    remaining_sum_insured: str
    unresolved: list[UnresolvedRuleResponse]
    range_low: str | None
    range_high: str | None
    invariants_ok: bool


# ---------------------------------------------------------------------------
# Counterfactual
# ---------------------------------------------------------------------------


class FieldChangeRequest(BaseModel):
    field: str
    from_val: Any
    to_val: Any


class CounterfactualRequest(BaseModel):
    base: SimulateRequest
    change: FieldChangeRequest


class CounterfactualResponse(BaseModel):
    result: SimulationResponse
    delta: str
    oop_delta: str
    changed_fields: list[str]
    interaction_residual: str


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------


class LoanMetricsResponse(BaseModel):
    label: str
    principal: str
    emi: str
    net_disbursed: str
    total_repayment: str
    total_interest: str
    total_cash_out: str
    apr_nominal: str
    apr_effective: str
    emi_pct_of_mean: str
    emi_pct_of_lean: str
    free_cash_avg_month: str
    free_cash_lean_month: str
    synthetic: bool = True


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class ActionStep(BaseModel):
    rank: int
    title: str
    why: str           # plain English, includes rupee figure
    effort: str        # e.g. "Retrieve renewal receipt"
    clause_id: str | None
    rupee_value: str   # Decimal as string


class PlanResponse(BaseModel):
    steps: list[ActionStep]
    draft_message: str
    unresolved_items: list[str]


# ---------------------------------------------------------------------------
# Session detail (Screen 2 gate state)
# ---------------------------------------------------------------------------


class MaterialFactState(BaseModel):
    rule_type: str
    # clause interpretation status, or "missing" when no clause exists
    status: str


class SessionDetailResponse(BaseModel):
    session_id: str
    mode: Literal["fixture", "live"]
    goal: str | None
    created_at: str
    has_document: bool
    simulation_ready: bool
    material_facts: list[MaterialFactState]


# ---------------------------------------------------------------------------
# Document pages (EvidenceViewer)
# ---------------------------------------------------------------------------


class DocumentPagesResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    pages: list[str]


# ---------------------------------------------------------------------------
# Hospital estimate + affordability (Screen 1/3 inputs, fixture demo)
# ---------------------------------------------------------------------------


class AffordabilityResponse(BaseModel):
    months: list[str]            # Decimal strings, 12 months of income
    month_labels: list[str]
    mean_income: str
    median_income: str
    lowest_income: str
    avg_free_cash: str
    lean_free_cash: str
    emergency_runway_months: str
    obligations_at_lean_pct: str
    savings: str
    essentials: str
    existing_emi: str
    synthetic: bool = True


class EstimateResponse(BaseModel):
    gross_bill: str
    nights: int
    room_rate_per_night: str
    charges: list[ChargeItemRequest]
    non_payable_total: str
    hospital_name: str
    procedure: str
    admission_date: str
    discharge_date: str
    sum_insured: str
    policy_month_at_admit: int
    # Derived server-side from this session's clauses so the frontend never
    # has to interpret policy parameters itself. None = not known yet.
    room_cap_per_day: str | None
    waiting_months_required: int | None
    affordability: AffordabilityResponse
    synthetic: bool = True


# ---------------------------------------------------------------------------
# Audit (Screen 5)
# ---------------------------------------------------------------------------


class AuditDocumentInfo(BaseModel):
    filename: str
    page_count: int
    pages_read: int
    retention: str


class AuditRunInfo(BaseModel):
    run_id: str
    created_at: str
    run_hash: str
    invariants_ok: bool
    insurer_payment: str | None
    out_of_pocket: str | None


class AuditResponse(BaseModel):
    session_id: str
    mode: Literal["fixture", "live"]
    document: AuditDocumentInfo | None
    engine_version: str
    provider_name: str
    provider_disclosure: str
    runs: list[AuditRunInfo]
    clauses_by_status: dict[str, int]
