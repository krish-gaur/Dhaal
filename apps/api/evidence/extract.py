"""
Evidence layer — clause extraction types and provider dispatch.

Design rules enforced here:
- ClauseStatus has exactly six legal values. No others.
- quote_found and interpretation_status are SEPARATE fields, never collapsed.
- The provider is selected by env var; FixtureProvider is the default.
- The LLM has no tools, no code execution. It extracts structure only.
- Document text passed to the LLM is wrapped in <document>…</document>.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ClauseStatus(StrEnum):
    """
    Exactly six statuses. No others are legal anywhere in the codebase.

    CRITICAL DISTINCTION:
    - quote_found: True means the text exists in the document.
    - interpretation_status: VERIFIED means the rule was correctly interpreted.
    These are two separate boolean facts. A clause can have quote_found=True
    but interpretation_status=UNVERIFIED if the wording is ambiguous.
    Never collapse them into a single "verified" checkmark.
    """

    VERIFIED = "verified"           # quote found AND interpretation unambiguous
    UNVERIFIED = "unverified"       # quote found, interpretation not confirmed
    UNKNOWN = "unknown"             # not found in document
    CONFLICTING = "conflicting"     # two clauses disagree on the same parameter
    USER_CONFIRMED = "user_confirmed"  # user explicitly accepted an interpretation
    SYNTHETIC = "synthetic"         # fixture / demo data


@dataclass(frozen=True)
class Verification:
    # quote_found and interpretation_status are ALWAYS separate.
    # Do not collapse them. See ClauseStatus docstring.
    schema_valid: bool
    quote_found: bool
    numbers_supported: bool
    interpretation_status: ClauseStatus
    reason: str


@dataclass(frozen=True)
class RuleParam:
    type: str
    params: dict[str, str]


@dataclass(frozen=True)
class Clause:
    clause_id: str
    document_id: str
    page: int
    char_start: int
    char_end: int
    quote: str
    quote_hash: str          # "sha256:<hex>"
    rule: RuleParam
    verification: Verification


# ---------------------------------------------------------------------------
# Provider Protocol
# ---------------------------------------------------------------------------


class ExtractionProvider(Protocol):
    def extract_clauses(
        self,
        page_texts: list[str],
        document_id: str,
    ) -> list[Clause]: ...

    @property
    def provider_name(self) -> str: ...


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def get_provider() -> ExtractionProvider:
    """
    Select provider based on environment variables.
    FixtureProvider is the default — no API key required.
    The fixture provider can run the entire demo with the network unplugged.
    """
    from evidence.providers.fixture import FixtureProvider

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from evidence.providers.anthropic import AnthropicProvider
            return AnthropicProvider()
        except ImportError:
            pass

    if os.getenv("OPENAI_API_KEY"):
        try:
            from evidence.providers.openai import OpenAIProvider
            return OpenAIProvider()
        except ImportError:
            pass

    return FixtureProvider()


# ---------------------------------------------------------------------------
# Supported rule types (for validation)
# ---------------------------------------------------------------------------

SUPPORTED_RULE_TYPES = {
    "room_rent_limit",
    "waiting_period",
    "non_payable",
    "co_payment",
    "deductible",
    "proportionate_deduction",
    "apportionment_base",
}

# Required params per rule type
REQUIRED_PARAMS: dict[str, set[str]] = {
    "room_rent_limit": {"basis", "value"},
    "waiting_period": {"months_required", "disease_type"},
    "non_payable": {"items"},
    "co_payment": {"pct"},
    "deductible": {"amount"},
    "proportionate_deduction": {"trigger"},
    "apportionment_base": {"scope"},
}
