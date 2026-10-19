"""
Loan and affordability engine.

APR is always computed from actual borrower cash flows (IRR via bisection).
It is never derived from the nominal rate alone.

Rounding: EMI uses ROUND_HALF_UP (standard financial convention).
APR is returned to full Decimal precision; display rounding to 2dp is the
responsibility of the caller.

The LLM never calls this module. All arithmetic is deterministic Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

_ZERO = Decimal("0")
_ONE = Decimal("1")
_TWELVE = Decimal("12")
_BISECT_LO = Decimal("0.000001")
_BISECT_HI = Decimal("10.0")
_CONVERGENCE = Decimal("1e-9")
_MAX_ITER = 200


# ---------------------------------------------------------------------------
# Loan data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoanOffer:
    label: str                   # "A" | "B" | "C"
    principal: Decimal
    nominal_rate_pa: Decimal     # e.g. Decimal("0.12") for 12%
    tenor_months: int
    processing_fee: Decimal
    gst_on_fee: Decimal
    credit_life_premium: Decimal


@dataclass(frozen=True)
class AffordabilityContext:
    income_months: list[Decimal]
    essentials: Decimal
    existing_emi: Decimal
    savings: Decimal


@dataclass(frozen=True)
class AffordabilitySummary:
    mean: Decimal
    median: Decimal
    lowest_observed: Decimal
    avg_free_cash: Decimal
    lean_free_cash: Decimal
    emergency_runway_months: Decimal
    obligations_at_lean_pct: Decimal


@dataclass(frozen=True)
class LoanMetrics:
    offer: LoanOffer
    net_disbursed: Decimal
    emi: Decimal
    total_repayment: Decimal
    total_interest: Decimal
    total_cash_out: Decimal
    apr_nominal: Decimal
    apr_effective: Decimal
    emi_pct_of_mean: Decimal
    emi_pct_of_lean: Decimal
    free_cash_avg_month: Decimal
    free_cash_lean_month: Decimal


class AprResult(NamedTuple):
    nominal: Decimal   # r * 12
    effective: Decimal  # (1 + r)^12 - 1


# ---------------------------------------------------------------------------
# Core financial functions
# ---------------------------------------------------------------------------


def emi(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """
    Compute the standard equated monthly instalment.

    Formula: P * r * (1+r)^n / ((1+r)^n - 1)
    where r = annual_rate / 12

    Edge cases:
    - annual_rate == 0: EMI = principal / months (no interest)
    - months <= 0: raises ValueError
    - principal <= 0: raises ValueError
    """
    if months <= 0:
        raise ValueError(f"tenor must be a positive integer, got {months}")
    if principal <= _ZERO:
        raise ValueError(f"principal must be positive, got {principal}")
    if annual_rate < _ZERO:
        raise ValueError(f"annual_rate must be >= 0, got {annual_rate}")

    if annual_rate == _ZERO:
        result = principal / Decimal(months)
    else:
        r = annual_rate / _TWELVE
        n = Decimal(months)
        factor = (_ONE + r) ** n
        result = principal * r * factor / (factor - _ONE)

    # EMI rounded to 2dp using ROUND_HALF_UP (standard financial convention)
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pv_of_payments(monthly_rate: Decimal, payment: Decimal, months: int) -> Decimal:
    """Present value of an annuity at monthly_rate."""
    r = monthly_rate
    n = months
    if r == _ZERO:
        return payment * Decimal(n)
    factor = (_ONE + r) ** n
    return payment * (factor - _ONE) / (r * factor)


def apr_from_cashflows(
    net_received: Decimal,
    payment: Decimal,
    months: int,
) -> AprResult:
    """
    Compute APR from actual borrower cash flows via bisection (IRR method).

    Solves: net_received = Σ_{k=1}^{months} payment / (1 + r)^k
    Convergence tolerance: |f(r)| < 1e-9
    Maximum iterations: 200

    Returns:
        nominal  = r * 12
        effective = (1 + r)^12 - 1

    Edge cases:
    - months <= 0: raises ValueError
    - net_received <= 0: raises ValueError
    - payment <= 0: raises ValueError
    - fee == 0 and no other costs: APR ≈ nominal rate (within 1bp)
    - rate == 0: special case, APR = 0
    """
    if months <= 0:
        raise ValueError(f"tenor must be positive, got {months}")
    if net_received <= _ZERO:
        raise ValueError(f"net_received must be positive, got {net_received}")
    if payment <= _ZERO:
        raise ValueError(f"payment must be positive, got {payment}")

    # Special case: if total payments == net_received (zero-rate instrument)
    total = payment * months
    if total == net_received:
        return AprResult(nominal=_ZERO, effective=_ZERO)

    def f(r: Decimal) -> Decimal:
        return _pv_of_payments(r, payment, months) - net_received

    lo = _BISECT_LO
    hi = _BISECT_HI

    f_lo = f(lo)
    f_hi = f(hi)

    if f_lo * f_hi > _ZERO:
        # Expand search range — very high rate instruments
        hi = Decimal("100.0")
        f_hi = f(hi)
        if f_lo * f_hi > _ZERO:
            raise ValueError(
                f"Bisection failed to bracket root: f({lo})={f_lo}, f({hi})={f_hi}"
            )

    for _ in range(_MAX_ITER):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid) < _CONVERGENCE:
            r = mid
            break
        if f_lo * f_mid < _ZERO:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid
    else:
        r = (lo + hi) / 2  # best approximation after max iterations

    nominal = r * _TWELVE
    effective = (_ONE + r) ** 12 - _ONE
    return AprResult(nominal=nominal, effective=effective)


# ---------------------------------------------------------------------------
# Affordability
# ---------------------------------------------------------------------------


def compute_affordability(ctx: AffordabilityContext) -> AffordabilitySummary:
    """
    Derive affordability metrics from 12 months of income history.

    Fixture values:
      mean = 31916.67, median = 32250.00, lowest = 22500
      avg_free_cash = 9216.67, lean_free_cash = -200.00
      emergency_runway = 1.54 months
      obligations_at_lean_pct = 100.9%
    """
    if not ctx.income_months:
        raise ValueError("income_months must not be empty")

    n = len(ctx.income_months)
    mean = sum(ctx.income_months, _ZERO) / Decimal(n)
    sorted_inc = sorted(ctx.income_months)
    if n % 2 == 1:
        median = sorted_inc[n // 2]
    else:
        median = (sorted_inc[n // 2 - 1] + sorted_inc[n // 2]) / 2

    lowest = sorted_inc[0]
    avg_free_cash = mean - ctx.essentials - ctx.existing_emi
    lean_free_cash = lowest - ctx.essentials - ctx.existing_emi
    # Emergency runway = savings / monthly obligations (essentials + existing EMI)
    # Spec: 35000 / (18500 + 4200) = 35000 / 22700 = 1.54 months
    obligations = ctx.essentials + ctx.existing_emi
    emergency_runway = ctx.savings / obligations if obligations > _ZERO else _ZERO
    obligations_pct = obligations / lowest if lowest > _ZERO else _ZERO

    return AffordabilitySummary(
        mean=mean,
        median=median,
        lowest_observed=lowest,
        avg_free_cash=avg_free_cash,
        lean_free_cash=lean_free_cash,
        emergency_runway_months=emergency_runway,
        obligations_at_lean_pct=obligations_pct,
    )


def compute_loan_metrics(
    offer: LoanOffer,
    affordability: AffordabilitySummary,
) -> LoanMetrics:
    """
    Compute full metrics for a loan offer including APR and affordability stress.
    """
    net_disbursed = (
        offer.principal
        - offer.processing_fee
        - offer.gst_on_fee
        - offer.credit_life_premium
    )

    monthly_emi = emi(offer.principal, offer.nominal_rate_pa, offer.tenor_months)
    total_repayment = monthly_emi * offer.tenor_months
    total_interest = total_repayment - offer.principal
    total_cash_out = total_repayment + offer.processing_fee + offer.gst_on_fee + offer.credit_life_premium

    apr = apr_from_cashflows(net_disbursed, monthly_emi, offer.tenor_months)

    emi_pct_of_mean = monthly_emi / affordability.mean if affordability.mean > _ZERO else _ZERO
    lean_income = affordability.lowest_observed
    emi_pct_of_lean = monthly_emi / lean_income if lean_income > _ZERO else _ZERO

    free_cash_avg = affordability.avg_free_cash - monthly_emi
    free_cash_lean = affordability.lean_free_cash - monthly_emi

    return LoanMetrics(
        offer=offer,
        net_disbursed=net_disbursed,
        emi=monthly_emi,
        total_repayment=total_repayment,
        total_interest=total_interest,
        total_cash_out=total_cash_out,
        apr_nominal=apr.nominal,
        apr_effective=apr.effective,
        emi_pct_of_mean=emi_pct_of_mean,
        emi_pct_of_lean=emi_pct_of_lean,
        free_cash_avg_month=free_cash_avg,
        free_cash_lean_month=free_cash_lean,
    )
