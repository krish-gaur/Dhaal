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
    Run all post-hoc invariants against a ClaimResult.
    Returns True if all pass. Raises InvariantError on first failure.

    Note: `result.remaining_sum_insured` is the sum insured remaining
    *after* this payment, so it must not be used as the ceiling for the
    payment itself — the engine enforces that ceiling by clamping before
    rounding. Here we only assert what can be verified from the result.
    """
    assert_non_negative(result.insurer_payment, result.out_of_pocket, result.gross_bill)
    assert_conservation(result.gross_bill, result.insurer_payment, result.out_of_pocket)
    # Every applied deduction must carry a citation. The engine fills an
    # honest "source page not recorded" fallback rather than inventing a
    # reference, so an empty citation here means a construction bug.
    # (Clause-level traceability — source_clause_id pointing at a real,
    # confirmed clause — is enforced by the API layer and its tests,
    # where clause records exist.)
    for d in result.deductions:
        if not d.citation:
            raise InvariantError(
                f"Deduction '{d.name}' (rule {d.rule_id}) has no citation"
            )
    if result.out_of_pocket > result.gross_bill:
        raise InvariantError(
            f"out_of_pocket={result.out_of_pocket} exceeds gross_bill={result.gross_bill}"
        )
    if result.range_low is not None and result.range_high is not None:
        if not (Decimal(0) <= result.range_low <= result.range_high <= result.gross_bill):
            raise InvariantError(
                f"Range invalid: low={result.range_low}, high={result.range_high}, "
                f"gross={result.gross_bill}"
            )
        if not (result.range_low <= result.out_of_pocket <= result.range_high):
            raise InvariantError(
                f"out_of_pocket={result.out_of_pocket} outside range "
                f"[{result.range_low}, {result.range_high}]"
            )
    return True
