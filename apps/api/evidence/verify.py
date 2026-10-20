"""
Deterministic clause verification pipeline.

This module is pure Python — no I/O, no LLM calls, no randomness.
It validates that extracted clauses actually match the source document.

CRITICAL DESIGN RULE:
  quote_found: True proves text exists.
  It does NOT prove the rule was interpreted correctly.
  These are separate fields, separate UI states, separate test suites.
  Never collapse them.

Verification pipeline (five steps, in order):
  1. Schema validation — rule type and params are valid
  2. Quote existence — normalised substring match against source page
  3. Number support — every numeral/% in the rule appears in the quote
  4. Rule-type validation — rule type is supported, all required params present
  5. Conflict detection — two rules for the same param with different values

Injection quarantine (runs before any extraction):
  Documents containing known injection markers are quarantined.
  They are not processed further. The API routes to manual entry.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from evidence.extract import (
    REQUIRED_PARAMS,
    SUPPORTED_RULE_TYPES,
    Clause,
    ClauseStatus,
    Verification,
)

# ---------------------------------------------------------------------------
# Injection quarantine markers
# ---------------------------------------------------------------------------

_INJECTION_MARKERS: list[str] = [
    "ignore previous",
    "you are now",
    "system:",
    "disregard",
    "forget all",
    "new instructions",
]

# Unicode codepoints that signal injection attempts:
# Zero-width chars (U+200B–U+200D, U+FEFF) and bidi overrides (U+202A–U+202E)
_INJECTION_CODEPOINTS: frozenset[int] = frozenset(
    list(range(0x200B, 0x200E))  # zero-width space, ZWNJ, ZWJ
    + [0xFEFF]                   # BOM / zero-width no-break space
    + list(range(0x202A, 0x202F))  # bidi override chars
)


def check_injection(text: str) -> bool:
    """
    Return True if the text contains known prompt-injection markers.

    Checked against:
    - Known text markers (case-insensitive)
    - Suspicious Unicode codepoints (zero-width, bidi overrides)
    """
    lower = text.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lower:
            return True
    return any(ord(ch) in _INJECTION_CODEPOINTS for ch in text)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------


def normalise(text: str) -> str:
    """
    Normalise text for quote matching.

    Applies:
    - NFKC Unicode normalisation
    - Whitespace collapse (any run of whitespace → single space)
    - Curly quote → straight quote
    - En/em dash → hyphen-minus
    - Soft hyphen removal (U+00AD)
    - Lowercase

    This is used for BOTH the source page text and the extracted quote,
    so the matching is symmetric.
    """
    # NFKC: compatibility decomposition + canonical composition
    text = unicodedata.normalize("NFKC", text)
    # Collapse all whitespace runs (including \n, \t, \r) to a single space
    text = re.sub(r"\s+", " ", text)
    # Curly/smart quotes → straight
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # '  '
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # "  "
    text = text.replace("\u201a", "'").replace("\u201b", "'")  # ‚  ‛
    text = text.replace("\u00ab", '"').replace("\u00bb", '"')  # «  »
    # En/em dash → hyphen
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2015", "-")
    # Soft hyphen removal
    text = text.replace("\u00ad", "")
    # Lowercase for case-insensitive matching
    return text.strip().lower()


def compute_quote_hash(quote: str) -> str:
    """SHA-256 of the raw (un-normalised) quote text."""
    digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ---------------------------------------------------------------------------
# Step 1 — Schema validation
# ---------------------------------------------------------------------------


def _validate_schema(clause: Clause) -> tuple[bool, str]:
    """Check that the rule type is supported and all required params are present."""
    rule_type = clause.rule.type
    if rule_type not in SUPPORTED_RULE_TYPES:
        return False, f"Unknown rule type: '{rule_type}'"

    required = REQUIRED_PARAMS.get(rule_type, set())
    missing = required - set(clause.rule.params.keys())
    if missing:
        return False, f"Missing required params for '{rule_type}': {sorted(missing)}"

    return True, ""


# ---------------------------------------------------------------------------
# Step 2 — Quote existence
# ---------------------------------------------------------------------------


def _check_quote_found(clause: Clause, page_texts: list[str]) -> tuple[bool, str]:
    """
    Check that clause.quote appears (normalised) in the stated page text.

    Returns (found, reason).
    """
    page_idx = clause.page - 1  # pages are 1-indexed
    if page_idx < 0 or page_idx >= len(page_texts):
        return False, f"Page {clause.page} out of range (document has {len(page_texts)} pages)"

    source = normalise(page_texts[page_idx])
    quote = normalise(clause.quote)

    if not quote:
        return False, "Extracted quote is empty after normalisation"

    if quote in source:
        return True, ""
    else:
        # Try a substring of the first 60 chars as a diagnostic hint
        snippet = quote[:60]
        return False, f"Quote not found in page {clause.page} (first 60 chars: '{snippet}...')"


# ---------------------------------------------------------------------------
# Step 3 — Number support
# ---------------------------------------------------------------------------

# Pattern: integers, decimals, percentages, currency amounts, durations
_NUMBER_PATTERN = re.compile(
    r"""
    (?:
        \d+(?:\.\d+)?%          # percentage like 1% or 1.5%
        |
        (?:rs\.?|₹|inr)\s*\d+  # currency amounts
        |
        \d+\s*(?:months?|days?|years?)  # durations
        |
        \d+(?:,\d+)*(?:\.\d+)?  # plain numbers including comma-formatted
        |
        \d+/\d+                 # ratios like 1/30
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _extract_numbers(text: str) -> list[str]:
    """Extract all numeric tokens from text."""
    return _NUMBER_PATTERN.findall(text.lower())


def _check_numbers_supported(clause: Clause) -> tuple[bool, str]:
    """
    Every numeral, percentage, and duration in the rule params must appear
    in the quoted text.

    A rule saying "1%" from a quote saying "2%" is rejected.
    """
    # Collect all values from rule params
    param_text = " ".join(str(v) for v in clause.rule.params.values())
    param_numbers = _extract_numbers(param_text)

    if not param_numbers:
        # No numbers in params — nothing to check
        return True, ""

    quote_normalised = normalise(clause.quote)
    missing: list[str] = []

    for num in param_numbers:
        # Normalise the number token for comparison
        num_norm = normalise(num)
        # Simple check: the number string appears somewhere in the quote
        if num_norm not in quote_normalised:
            missing.append(num)

    if missing:
        return False, f"Numbers in rule not found in quote: {missing}"

    return True, ""


# ---------------------------------------------------------------------------
# Step 4 — Rule-type validation (already covered by schema, confirm here)
# ---------------------------------------------------------------------------


def _validate_rule_type(clause: Clause) -> tuple[bool, str]:
    """Confirm rule type is a known supported type."""
    if clause.rule.type not in SUPPORTED_RULE_TYPES:
        return False, f"Unsupported rule type: '{clause.rule.type}'"
    return True, ""


# ---------------------------------------------------------------------------
# Step 5 — Conflict detection
# ---------------------------------------------------------------------------


def detect_conflicts(clauses: list[Clause]) -> list[Clause]:
    """
    Check all clause pairs for conflicting values on the same parameter.

    Two clauses conflict if they have:
    - the same rule.type
    - different values for the same param key

    Both are marked CONFLICTING. Neither is applied to the simulation.
    """
    # Group by rule type
    by_type: dict[str, list[Clause]] = {}
    for c in clauses:
        by_type.setdefault(c.rule.type, []).append(c)

    conflicting_ids: set[str] = set()

    for group in by_type.values():
        if len(group) < 2:
            continue
        # Check if any shared param has different values
        for i, c1 in enumerate(group):
            for c2 in group[i + 1 :]:
                shared_keys = set(c1.rule.params) & set(c2.rule.params)
                for key in shared_keys:
                    if c1.rule.params[key] != c2.rule.params[key]:
                        conflicting_ids.add(c1.clause_id)
                        conflicting_ids.add(c2.clause_id)

    # Rebuild list with CONFLICTING status where needed
    result: list[Clause] = []
    for c in clauses:
        if c.clause_id in conflicting_ids:
            new_verification = replace(
                c.verification,
                interpretation_status=ClauseStatus.CONFLICTING,
                reason=(
                    f"Conflicts with another '{c.rule.type}' clause "
                    f"on the same parameter"
                ),
            )
            result.append(
                Clause(
                    clause_id=c.clause_id,
                    document_id=c.document_id,
                    page=c.page,
                    char_start=c.char_start,
                    char_end=c.char_end,
                    quote=c.quote,
                    quote_hash=c.quote_hash,
                    rule=c.rule,
                    verification=new_verification,
                )
            )
        else:
            result.append(c)

    return result


# ---------------------------------------------------------------------------
# Main verification entry point
# ---------------------------------------------------------------------------


def verify_clause(clause: Clause, page_texts: list[str]) -> Clause:
    """
    Run the full 4-step verification pipeline on a single clause.
    Returns a new Clause (immutable) with updated verification fields.

    Steps run in order:
    1. Schema validation
    2. Quote existence
    3. Number support
    4. Rule-type validation

    Status assignment:
    - All four pass → VERIFIED (if not synthetic)
    - Quote found but numbers/interpretation unclear → UNVERIFIED
    - Schema invalid or rule type unknown → UNKNOWN
    - User has confirmed → USER_CONFIRMED (preserved, not overridden)
    - Synthetic fixtures → SYNTHETIC (preserved, not overridden)
    """
    # Preserve statuses that come from outside the pipeline
    current_status = clause.verification.interpretation_status
    if current_status in (ClauseStatus.USER_CONFIRMED, ClauseStatus.SYNTHETIC):
        return clause

    # Step 1 — Schema
    schema_ok, schema_reason = _validate_schema(clause)

    # Step 2 — Quote existence
    if schema_ok:
        quote_ok, quote_reason = _check_quote_found(clause, page_texts)
    else:
        quote_ok, quote_reason = False, "Schema invalid — skipping quote check"

    # Step 3 — Number support
    if quote_ok:
        numbers_ok, numbers_reason = _check_numbers_supported(clause)
    else:
        numbers_ok, numbers_reason = False, "Quote not found — skipping number check"

    # Step 4 — Rule type (redundant with schema, kept for explicitness)
    rule_ok, rule_reason = _validate_rule_type(clause)

    # Determine status
    if not schema_ok or not rule_ok:
        status = ClauseStatus.UNKNOWN
        reason = schema_reason or rule_reason
    elif not quote_ok:
        status = ClauseStatus.UNVERIFIED
        reason = quote_reason
    elif not numbers_ok:
        status = ClauseStatus.UNVERIFIED
        reason = numbers_reason
    else:
        status = ClauseStatus.VERIFIED
        reason = ""

    new_verification = Verification(
        schema_valid=schema_ok,
        quote_found=quote_ok,
        numbers_supported=numbers_ok,
        interpretation_status=status,
        reason=reason,
    )

    return Clause(
        clause_id=clause.clause_id,
        document_id=clause.document_id,
        page=clause.page,
        char_start=clause.char_start,
        char_end=clause.char_end,
        quote=clause.quote,
        quote_hash=clause.quote_hash,
        rule=clause.rule,
        verification=new_verification,
    )


def verify_all(clauses: list[Clause], page_texts: list[str]) -> list[Clause]:
    """Run verify_clause on all clauses, then detect conflicts."""
    verified = [verify_clause(c, page_texts) for c in clauses]
    return detect_conflicts(verified)
