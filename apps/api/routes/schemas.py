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
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ChargeItemRequest(BaseModel):
    name: str
    amount: str   # Decimal as string
    nights: int | None = None


class SimulationAssumptions(BaseModel):
    policy_month_at_admit: int
    remaining_sum_insured: str
    apportionment_base: str = "surgeon_ot_diagnostics"
    continuity_confirmed: bool = False


class SimulateRequest(BaseModel):
    gross: str
    charges: list[ChargeItemRequest]
    room_rate_per_night: str
    nights: int
    assumptions: SimulationAssumptions


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
