"""
Conservation and monotonicity invariants for the claim engine.

These are called at the engine boundary, not in tests alone.
A violation is a hard error — the result is never returned to the caller.
"""

from __future__ import annotations

from decimal import Decimal

from engine.rules import ClaimResult, InvariantError


def assert_conservation(
    gross: Decimal,
    insurer: Decimal,
    oop: Decimal,
) -> None:
    """
    insurer_payment + out_of_pocket == gross_bill must hold exactly.

    Rounding rule: insurer is ROUND_FLOOR to the rupee.
    Therefore oop = gross - insurer, which is exact.
    Any deviation indicates a logic error in the waterfall.
    """
    if insurer + oop != gross:
        raise InvariantError(
            f"Conservation violated: insurer={insurer} + oop={oop} = {insurer + oop} "
            f"!= gross={gross}. Delta={gross - (insurer + oop)}"
        )


def assert_non_negative(insurer: Decimal, oop: Decimal, gross: Decimal) -> None:
    """insurer and oop must both be >= 0."""
    if insurer < Decimal(0):
        raise InvariantError(f"insurer_payment is negative: {insurer}")
    if oop < Decimal(0):
        raise InvariantError(f"out_of_pocket is negative: {oop}")
    if gross < Decimal(0):
        raise InvariantError(f"gross_bill is negative: {gross}")


def assert_insurer_within_sum_insured(
    insurer: Decimal, remaining_si: Decimal
) -> None:
    """insurer_payment cannot exceed remaining sum insured."""
    if insurer > remaining_si:
        raise InvariantError(
            f"insurer_payment={insurer} exceeds remaining_sum_insured={remaining_si}"
        )


def check_all(result: ClaimResult) -> bool:
    """
    Run all invariants against a ClaimResult.
    Returns True if all pass. Raises InvariantError on first failure.
    Callers should catch InvariantError and set invariants_ok=False before
    blocking the response.
    """
    assert_non_negative(result.insurer_payment, result.out_of_pocket, result.gross_bill)
    assert_conservation(result.gross_bill, result.insurer_payment, result.out_of_pocket)
    assert_insurer_within_sum_insured(result.insurer_payment, result.remaining_sum_insured)
    return True
