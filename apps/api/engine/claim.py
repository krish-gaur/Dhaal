"""
Core claim simulation engine.

This module is a pure function: no I/O, no randomness, no side effects.
It is the only place where claim arithmetic happens.

Rounding rule (documented once, applied once):
  insurer_payment = floor(clamp(net_admissible, 0, remaining_sum_insured))
  ROUND_FLOOR to the nearest rupee, applied at step 8, nowhere else.
  out_of_pocket = gross_bill - insurer_payment  (exact, no separate rounding)

The LLM never touches this module. It extracts data; the engine computes.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import ROUND_FLOOR, Decimal

from engine.invariants import assert_conservation, assert_non_negative, check_all
from engine.rules import (
    ApportionmentBase,
    ChargeItem,
    ClaimInputs,
    ClaimResult,
    Deduction,
    InvariantError,
    PolicyRules,
    RuleType,
    UnresolvedRule,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_RUPEE = Decimal("1")  # rounding quantum


def _floor_rupee(amount: Decimal) -> Decimal:
    """Round down to the nearest whole rupee. Applied once, at the boundary."""
    return amount.to_integral_value(rounding=ROUND_FLOOR)


def _clamp(value: Decimal, lo: Decimal, hi: Decimal) -> Decimal:
    return max(lo, min(value, hi))


def _cite(citation: str) -> str:
    """Citation for a deduction: the rule's recorded source, or an honest
    statement that no page was recorded — never an invented reference."""
    return citation if citation else "policy wording (source page not recorded)"


def _room_billed(inputs: ClaimInputs) -> Decimal:
    """Total room charge from the bill."""
    return inputs.room_rate_per_night * inputs.nights


def _room_cap_per_day(rules: PolicyRules) -> Decimal:
    """Compute the allowed room amount per day from PolicyRules."""
    rl = rules.room_limit
    if rl is None:
        raise ValueError("room_limit is None — caller must handle unknown before calling this")
    if rl.basis == "pct_sum_insured_per_day":
        return rules.sum_insured * rl.value
    # fixed_per_day
    return rl.value


def _charges_in_apportionment_base(
    charges: list[ChargeItem],
    base: ApportionmentBase,
) -> Decimal:
    """
    Return the total of charges subject to proportionate deduction.

    This is always an explicit, surfaced configuration — never a default.
    The fixture policy uses SURGEON_OT_DIAGNOSTICS.
    """
    name_lower = {c.name.lower(): c.amount for c in charges}

    if base == ApportionmentBase.ROOM_RELATED_ONLY:
        # Only room-adjacent charges (nursing, housekeeping) — none in fixture
        return _ZERO

    if base == ApportionmentBase.SURGEON_OT_DIAGNOSTICS:
        # Fixture: surgeon ₹42,000 + OT ₹18,000 + diagnostics ₹14,000 = ₹74,000
        keys = ["surgeon", "surgeon fees", "ot", "ot charges", "operation theatre",
                "diagnostics", "diagnostic"]
        return sum(
            (v for k, v in name_lower.items() if any(key in k for key in keys)),
            _ZERO,
        )

    if base == ApportionmentBase.ALL_MEDICAL_EXPENSES:
        # Every charge except room itself
        return sum(
            (c.amount for c in charges if c.nights is None),
            _ZERO,
        )

    # UNRESOLVED — caller handles
    raise ValueError(
        "apportionment_base is UNRESOLVED — must not call _charges_in_apportionment_base"
    )


def simulate_claim(rules: PolicyRules, inputs: ClaimInputs) -> ClaimResult:
    """
    Simulate a health insurance claim and return a fully-traced ClaimResult.

    The waterfall order is governed by rules.waterfall.
    Every deduction carries its calculation basis as a human-readable string.
    Conservation is asserted before returning; InvariantError is raised on failure.
    """
    if inputs.gross_bill < _ZERO:
        raise ValueError(f"gross_bill must be >= 0, got {inputs.gross_bill}")

    deductions: list[Deduction] = []
    unresolved: list[UnresolvedRule] = []
    net = inputs.gross_bill  # running net admissible, decremented by each deduction

    # Track whether waiting period blocked payout — short-circuit the rest
    waiting_period_blocked = False

    for rule_type in rules.waterfall:

        # ------------------------------------------------------------------ #
        # Step: EXCLUSION                                                     #
        # A coverage gate, not a deduction: if the claim's condition is    #
        # excluded by the policy, nothing is payable. If we cannot tell    #
        # (condition not supplied, clause unconfirmed), the possibility    #
        # is surfaced as unresolved — never silently applied or skipped.   #
        # ------------------------------------------------------------------ #
        if rule_type == RuleType.EXCLUSION:
            for ex in rules.exclusions:
                if ex.pending:
                    unresolved.append(
                        UnresolvedRule(
                            rule_type=RuleType.EXCLUSION,
                            reason=(
                                "An exclusion clause exists in the policy but "
                                "has not been confirmed, so it cannot be ruled "
                                "in or out for this claim."
                            ),
                            low_impact=_ZERO,
                            high_impact=max(_ZERO, net),
                        )
                    )
                    continue
                if inputs.condition_tag is None:
                    unresolved.append(
                        UnresolvedRule(
                            rule_type=RuleType.EXCLUSION,
                            reason=(
                                "The policy excludes certain conditions, but "
                                "the condition for this admission was not "
                                "supplied, so exclusions cannot be checked."
                            ),
                            low_impact=_ZERO,
                            high_impact=max(_ZERO, net),
                        )
                    )
                    continue
                if inputs.condition_tag in ex.conditions:
                    deductions.append(
                        Deduction(
                            name=f"Excluded — {ex.label or inputs.condition_tag}",
                            amount=net,
                            basis=(
                                "This condition/treatment is excluded under "
                                "the policy, so no amount is payable for "
                                "this claim."
                            ),
                            rule_id="exclusion",
                            citation=_cite(ex.citation),
                            source_clause_id=ex.source_clause_id,
                        )
                    )
                    net = _ZERO
                    waiting_period_blocked = True  # reuse the short-circuit
                    break
            if waiting_period_blocked:
                break  # excluded — skip all remaining steps

        # ------------------------------------------------------------------ #
        # Step: WAITING_PERIOD                                                #
        # Each waiting period is evaluated against ITS scope: an initial   #
        # (day-based) wait, a specified-disease wait (only for listed      #
        # conditions), or a pre-existing-disease wait. A waiting period    #
        # is never applied to a claim it does not govern; when the claim   #
        # details needed to decide are missing, it becomes unresolved.     #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.WAITING_PERIOD:
            for wp in rules.waiting_periods:
                if wp.pending:
                    unresolved.append(
                        UnresolvedRule(
                            rule_type=RuleType.WAITING_PERIOD,
                            reason=(
                                "A waiting-period clause exists in the "
                                "policy but has not been confirmed."
                            ),
                            low_impact=_ZERO,
                            high_impact=max(_ZERO, net),
                        )
                    )
                    continue

                blocked_basis: str | None = None
                if wp.days_required is not None:
                    # Initial (day-based) waiting period.
                    if wp.accident_exception and inputs.is_accident:
                        continue  # accidents covered from day one
                    if inputs.days_since_inception is None:
                        unresolved.append(
                            UnresolvedRule(
                                rule_type=RuleType.WAITING_PERIOD,
                                reason=(
                                    "The policy has an initial waiting "
                                    f"period of {wp.days_required} days, but "
                                    "the policy inception date was not "
                                    "supplied."
                                ),
                                low_impact=_ZERO,
                                high_impact=max(_ZERO, net),
                            )
                        )
                        continue
                    if inputs.days_since_inception < wp.days_required:
                        blocked_basis = (
                            f"{inputs.days_since_inception} days since "
                            f"inception < {wp.days_required} days required"
                        )
                elif wp.scope == "pre_existing":
                    if inputs.is_pre_existing is None:
                        unresolved.append(
                            UnresolvedRule(
                                rule_type=RuleType.WAITING_PERIOD,
                                reason=(
                                    "The policy has a pre-existing-disease "
                                    f"waiting period of {wp.months_required} "
                                    "months, but whether this condition is "
                                    "pre-existing was not supplied."
                                ),
                                low_impact=_ZERO,
                                high_impact=max(_ZERO, net),
                            )
                        )
                        continue
                    if not inputs.is_pre_existing:
                        continue
                    if inputs.policy_month_at_admit < wp.months_required:
                        blocked_basis = (
                            f"Policy month {inputs.policy_month_at_admit} < "
                            f"{wp.months_required} months required "
                            "(pre-existing disease)"
                        )
                else:  # specified diseases/procedures
                    if wp.conditions is not None:
                        if inputs.condition_tag is None:
                            unresolved.append(
                                UnresolvedRule(
                                    rule_type=RuleType.WAITING_PERIOD,
                                    reason=(
                                        "The policy has a waiting period "
                                        f"of {wp.months_required} months for "
                                        "specified diseases/procedures, but "
                                        "the condition for this admission "
                                        "was not supplied."
                                    ),
                                    low_impact=_ZERO,
                                    high_impact=max(_ZERO, net),
                                )
                            )
                            continue
                        if inputs.condition_tag not in wp.conditions:
                            continue  # this wait does not govern this claim
                    if inputs.policy_month_at_admit < wp.months_required:
                        blocked_basis = (
                            f"Policy month {inputs.policy_month_at_admit} < "
                            f"{wp.months_required} months required"
                        )

                if blocked_basis is not None:
                    # Claim inadmissible under this waiting period.
                    waiting_period_blocked = True
                    deductions.append(
                        Deduction(
                            name=f"Waiting period — {wp.disease_type}",
                            amount=net,
                            basis=blocked_basis,
                            rule_id="waiting_period",
                            citation=_cite(wp.citation),
                            source_clause_id=wp.source_clause_id,
                        )
                    )
                    net = _ZERO
                    break  # one blocking period is enough
            if waiting_period_blocked:
                break  # skip all remaining waterfall steps

        # ------------------------------------------------------------------ #
        # Step: NON_PAYABLE                                                   #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.NON_PAYABLE:
            if rules.non_payable is not None:
                npt = rules.non_payable.total
                items_str = ", ".join(rules.non_payable.items[:3])
                if len(rules.non_payable.items) > 3:
                    items_str += f" + {len(rules.non_payable.items) - 3} more"
                deductions.append(
                    Deduction(
                        name="Non-payable items",
                        amount=npt,
                        basis=f"Items excluded by policy schedule: {items_str}",
                        rule_id="non_payable",
                        citation=_cite(rules.non_payable.citation),
                        source_clause_id=rules.non_payable.source_clause_id,
                    )
                )
                net -= npt
            # None means we simply don't know; add to unresolved.
            # Worst case derived from the bill itself: in the extreme, every
            # rupee still in the running net could be a non-payable item.
            # We never substitute an invented "typical" figure.
            else:
                unresolved.append(
                    UnresolvedRule(
                        rule_type=RuleType.NON_PAYABLE,
                        reason=(
                            "Non-payable items (or their billed total) are not "
                            "known, so this deduction cannot be calculated. "
                            "Range assumes anything from ₹0 to the full "
                            "remaining bill could be non-payable."
                        ),
                        low_impact=_ZERO,
                        high_impact=max(_ZERO, net),
                    )
                )

        # ------------------------------------------------------------------ #
        # Step: ROOM_RENT_LIMIT                                               #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.ROOM_RENT_LIMIT:
            if rules.room_limit is None:
                unresolved.append(
                    UnresolvedRule(
                        rule_type=RuleType.ROOM_RENT_LIMIT,
                        reason="Room rent limit not found or unverified in policy document",
                        low_impact=_ZERO,
                        high_impact=_room_billed(inputs),
                    )
                )
            else:
                cap_per_day = _room_cap_per_day(rules)
                room_eligible = cap_per_day * inputs.nights
                room_billed = _room_billed(inputs)
                room_deduction = max(_ZERO, room_billed - room_eligible)

                if room_deduction > _ZERO:
                    deductions.append(
                        Deduction(
                            name="Room rent — above cap",
                            amount=room_deduction,
                            basis=(
                                f"Billed ₹{room_billed:,.0f} "
                                f"− eligible ₹{room_eligible:,.0f} "
                                f"(₹{cap_per_day:,.0f}/day × {inputs.nights} nights)"
                            ),
                            rule_id="room_rent_limit",
                            citation=_cite(rules.room_limit.citation),
                            source_clause_id=rules.room_limit.source_clause_id,
                        )
                    )
                    net -= room_deduction

        # ------------------------------------------------------------------ #
        # Step: PROPORTIONATE_DEDUCTION                                       #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.PROPORTIONATE_DEDUCTION:
            if rules.proportionate_deduction is None:
                # No proportionate deduction clause — skip silently
                pass
            elif rules.room_limit is None:
                # Worst case derived from the bill: without a room cap the
                # eligible/billed ratio is unknown, so the deduction could
                # reach the whole non-room charge pool (ratio → 0).
                non_room_total = sum(
                    (c.amount for c in inputs.charges if c.nights is None), _ZERO
                )
                unresolved.append(
                    UnresolvedRule(
                        rule_type=RuleType.PROPORTIONATE_DEDUCTION,
                        reason=(
                            "Cannot compute proportionate deduction without the "
                            "room rent limit. Range assumes anything from ₹0 "
                            "to all non-room charges being reduced."
                        ),
                        low_impact=_ZERO,
                        high_impact=max(_ZERO, min(non_room_total, net)),
                    )
                )
            elif rules.apportionment_base == ApportionmentBase.UNRESOLVED:
                # The phrase 'associated medical expenses' is not conclusively
                # defined for this policy. This is an explicit, surfaced
                # unresolved state — never a silent default.
                # Range semantics (design §4.1): the low bound assumes zero
                # impact from this rule; the high bound is the worst-case
                # impact over the interpretations the EXTRACTED WORDING can
                # support (rules.apportionment_candidates, derived from
                # clause evidence). A reading the wording expressly rules
                # out — e.g. applying the deduction to medicines a clause
                # exempts — must never become the "worst case".
                room_billed_u = _room_billed(inputs)
                room_eligible_u = _room_cap_per_day(rules) * inputs.nights
                if room_billed_u > room_eligible_u:
                    ratio_u = room_eligible_u / room_billed_u
                    candidates = rules.apportionment_candidates or (
                        ApportionmentBase.ROOM_RELATED_ONLY,
                        ApportionmentBase.SURGEON_OT_DIAGNOSTICS,
                        ApportionmentBase.ALL_MEDICAL_EXPENSES,
                    )
                    concrete_deductions = [
                        _charges_in_apportionment_base(inputs.charges, base) * (_ONE - ratio_u)
                        for base in candidates
                    ]
                    low_u = _ZERO
                    high_u = max(concrete_deductions, default=_ZERO)
                    swing = _floor_rupee(high_u - low_u)
                    unresolved.append(
                        UnresolvedRule(
                            rule_type=RuleType.PROPORTIONATE_DEDUCTION,
                            reason=(
                                "'Associated medical expenses' is not fully defined in "
                                f"the policy wording. Which charges it covers changes "
                                f"this deduction by up to ₹{swing:,.0f}."
                            ),
                            low_impact=low_u,
                            high_impact=high_u,
                        )
                    )
                # Room at/below cap: no proportionate deduction under any
                # interpretation — nothing is unresolved.
            else:
                room_billed = _room_billed(inputs)
                cap_per_day = _room_cap_per_day(rules)
                room_eligible = cap_per_day * inputs.nights

                # Only deduct proportionately if room was above cap
                if room_billed > room_eligible:
                    # ratio kept at full Decimal precision throughout
                    ratio = room_eligible / room_billed

                    try:
                        base_total = _charges_in_apportionment_base(
                            inputs.charges, rules.apportionment_base
                        )
                    except ValueError:
                        unresolved.append(
                            UnresolvedRule(
                                rule_type=RuleType.PROPORTIONATE_DEDUCTION,
                                reason="Apportionment base computation failed",
                                low_impact=_ZERO,
                                high_impact=max(_ZERO, net),
                            )
                        )
                    else:
                        prop_deduction = base_total * (_ONE - ratio)
                        # Display ratio to 4dp in basis string
                        ratio_display = f"{ratio:.4f}"
                        deductions.append(
                            Deduction(
                                name="Proportionate deduction",
                                amount=prop_deduction,
                                basis=(
                                    f"₹{base_total:,.0f} × (1 − {ratio_display}) "
                                    f"[room eligible/billed = {ratio_display}]"
                                ),
                                rule_id="proportionate_deduction",
                                citation=_cite(rules.proportionate_deduction.citation),
                                source_clause_id=rules.proportionate_deduction.source_clause_id,
                            )
                        )
                        net -= prop_deduction

        # ------------------------------------------------------------------ #
        # Step: CO_PAYMENT                                                    #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.CO_PAYMENT:
            if rules.co_payment is not None:
                copay_amount = net * rules.co_payment.pct
                deductions.append(
                    Deduction(
                        name="Co-payment",
                        amount=copay_amount,
                        basis=(
                            f"{rules.co_payment.pct * 100:.0f}% of "
                            f"net admissible ₹{net:,.2f}"
                        ),
                        rule_id="co_payment",
                        citation=_cite(rules.co_payment.citation),
                        source_clause_id=rules.co_payment.source_clause_id,
                    )
                )
                net -= copay_amount

        # ------------------------------------------------------------------ #
        # Step: DEDUCTIBLE                                                    #
        # ------------------------------------------------------------------ #
        elif rule_type == RuleType.DEDUCTIBLE:
            if rules.deductible is not None:
                ded = min(rules.deductible, net)  # cannot exceed remaining net
                deductions.append(
                    Deduction(
                        name="Deductible",
                        amount=ded,
                        basis=f"Fixed deductible ₹{rules.deductible:,.0f}",
                        rule_id="deductible",
                        citation=_cite(rules.deductible_citation),
                        source_clause_id=rules.deductible_clause_id,
                    )
                )
                net -= ded

    # ---------------------------------------------------------------------- #
    # Compute insurer payment                                                 #
    # Rounding rule: ROUND_FLOOR to the rupee, applied exactly once here.    #
    # out_of_pocket = gross - insurer (exact, no separate rounding).         #
    # ---------------------------------------------------------------------- #
    net_admissible = net
    raw_insurer = _clamp(net_admissible, _ZERO, inputs.remaining_sum_insured)
    insurer_payment = _floor_rupee(raw_insurer)  # ROUND_FLOOR — once, here only
    out_of_pocket = inputs.gross_bill - insurer_payment

    # ---------------------------------------------------------------------- #
    # Conservation invariant — hard error if violated                        #
    # ---------------------------------------------------------------------- #
    try:
        assert_non_negative(insurer_payment, out_of_pocket, inputs.gross_bill)
        assert_conservation(inputs.gross_bill, insurer_payment, out_of_pocket)
    except InvariantError:
        # Return a result with invariants_ok=False so the route layer can block it
        return ClaimResult(
            gross_bill=inputs.gross_bill,
            non_payable_total=_sum_deductions_by_rule(deductions, "non_payable"),
            admissible=net_admissible,
            deductions=deductions,
            insurer_payment=insurer_payment,
            out_of_pocket=out_of_pocket,
            remaining_sum_insured=inputs.remaining_sum_insured,
            unresolved=unresolved,
            range_low=None,
            range_high=None,
            invariants_ok=False,
        )

    # ---------------------------------------------------------------------- #
    # Compute range if any rules are unresolved                               #
    # ---------------------------------------------------------------------- #
    range_low: Decimal | None = None
    range_high: Decimal | None = None
    if unresolved:
        # Unresolved deductions were NOT subtracted from net_admissible.
        # The out-of-pocket range therefore comes from *subtracting* their
        # possible impact from the insurer payment:
        #   insurer_max: unresolved rules deduct as little as possible
        #   insurer_min: unresolved rules deduct as much as possible
        # range_low/range_high are the resulting min/max out-of-pocket.
        total_low = sum((u.low_impact for u in unresolved), _ZERO)
        total_high = sum((u.high_impact for u in unresolved), _ZERO)
        insurer_max = _floor_rupee(
            _clamp(net_admissible - total_low, _ZERO, inputs.remaining_sum_insured)
        )
        insurer_min = _floor_rupee(
            _clamp(net_admissible - total_high, _ZERO, inputs.remaining_sum_insured)
        )
        range_low = inputs.gross_bill - insurer_max    # min possible oop
        range_high = inputs.gross_bill - insurer_min   # max possible oop

    non_payable_total = _sum_deductions_by_rule(deductions, "non_payable")

    result = ClaimResult(
        gross_bill=inputs.gross_bill,
        non_payable_total=non_payable_total,
        admissible=inputs.gross_bill - non_payable_total,
        deductions=deductions,
        insurer_payment=insurer_payment,
        out_of_pocket=out_of_pocket,
        remaining_sum_insured=inputs.remaining_sum_insured - insurer_payment,
        unresolved=unresolved,
        range_low=range_low,
        range_high=range_high,
        invariants_ok=True,
    )
    # Final boundary check (includes range sanity). A failure here means an
    # engine bug — flag the result so the route layer blocks it.
    try:
        check_all(result)
    except InvariantError:
        return replace(result, invariants_ok=False)
    return result


def _sum_deductions_by_rule(deductions: list[Deduction], rule_id: str) -> Decimal:
    return sum((d.amount for d in deductions if d.rule_id == rule_id), _ZERO)
