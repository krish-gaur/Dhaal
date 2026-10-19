"""
Fixture provider — returns pre-verified clause extractions from policy_clauses.json.

This is the default provider when no API key is present.
It makes zero network calls and runs fully offline.
The entire five-screen demo works through this provider alone.

All clauses are labelled SYNTHETIC in the verification status.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from evidence.extract import (
    Clause,
    ClauseStatus,
    RuleParam,
    Verification,
)

# Path to fixtures directory — relative to repo root
import os

# DHAAL_FIXTURES_DIR env var overrides path resolution (useful in tests and CI)
_FIXTURES_DIR = Path(
    os.getenv("DHAAL_FIXTURES_DIR")
    or str(Path(__file__).parent.parent.parent.parent.parent / "fixtures")
)


def _load_fixture_clauses() -> list[dict]:  # type: ignore[type-arg]
    """Load policy_clauses.json from the fixtures directory."""
    path = _FIXTURES_DIR / "policy_clauses.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Fixture file not found: {path}. "
            "Run fixtures/generate_pdf.py to generate fixture files."
        )
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["clauses"]  # type: ignore[no-any-return]


def _dict_to_clause(raw: dict) -> Clause:  # type: ignore[type-arg]
    """Deserialise a clause dict from policy_clauses.json into a Clause dataclass."""
    v = raw["verification"]
    verification = Verification(
        schema_valid=v["schema_valid"],
        quote_found=v["quote_found"],
        numbers_supported=v["numbers_supported"],
        interpretation_status=ClauseStatus(v["interpretation_status"]),
        reason=v.get("reason", ""),
    )
    rule_raw = raw["rule"]
    rule = RuleParam(
        type=rule_raw["type"],
        params=rule_raw["params"],
    )
    return Clause(
        clause_id=raw["clause_id"],
        document_id=raw["document_id"],
        page=raw["page"],
        char_start=raw["char_start"],
        char_end=raw["char_end"],
        quote=raw["quote"],
        quote_hash=raw["quote_hash"],
        rule=rule,
        verification=verification,
    )


class FixtureProvider:
    """
    Returns pre-built clause extractions from fixtures/policy_clauses.json.

    Zero network calls. Works offline. First-class path, not a fallback.
    All clauses carry status=SYNTHETIC, visibly labelled in the UI.
    """

    @property
    def provider_name(self) -> str:
        return "fixture"

    def extract_clauses(
        self,
        page_texts: list[str],
        document_id: str,
    ) -> list[Clause]:
        """
        Return fixture clauses, re-keyed to the given document_id.
        page_texts is accepted but not used — the fixture has pre-baked offsets.
        """
        raw_clauses = _load_fixture_clauses()
        return [
            Clause(
                clause_id=raw["clause_id"],
                document_id=document_id,  # re-key to current session's document
                page=raw["page"],
                char_start=raw["char_start"],
                char_end=raw["char_end"],
                quote=raw["quote"],
                quote_hash=raw["quote_hash"],
                rule=RuleParam(
                    type=raw["rule"]["type"],
                    params=raw["rule"]["params"],
                ),
                verification=Verification(
                    schema_valid=raw["verification"]["schema_valid"],
                    quote_found=raw["verification"]["quote_found"],
                    numbers_supported=raw["verification"]["numbers_supported"],
                    interpretation_status=ClauseStatus(
                        raw["verification"]["interpretation_status"]
                    ),
                    reason=raw["verification"].get("reason", ""),
                ),
            )
            for raw in raw_clauses
        ]
