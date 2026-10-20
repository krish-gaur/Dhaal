"""
Fixture data loaders shared by the estimate, loans, and plan routes.

All fixture files are synthetic demo data. Loaders fail loudly (500) if a
fixture file is missing — they never substitute invented numbers.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException

from engine.loans import AffordabilityContext, LoanOffer

_FIXTURES_DIR = Path(
    os.getenv("DHAAL_FIXTURES_DIR")
    or str(Path(__file__).parent.parent.parent.parent / "fixtures")
)


def fixtures_dir() -> Path:
    return _FIXTURES_DIR


def _load_json(filename: str) -> dict:  # type: ignore[type-arg]
    path = _FIXTURES_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Fixture file not found: {filename}")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_loan_offers() -> list[LoanOffer]:
    data = _load_json("loan_offers.json")
    offers: list[LoanOffer] = []
    for o in data["offers"]:
        offers.append(
            LoanOffer(
                label=str(o["label"]),
                principal=Decimal(str(o["principal"])),
                nominal_rate_pa=Decimal(str(o["nominal_rate_pa"])),
                tenor_months=int(o["tenor_months"]),
                processing_fee=Decimal(str(o["processing_fee"])),
                gst_on_fee=Decimal(str(o["gst_on_fee"])),
                credit_life_premium=Decimal(str(o["credit_life_premium"])),
            )
        )
    return offers


def load_income_raw() -> dict:  # type: ignore[type-arg]
    return _load_json("income_history.json")


def load_affordability_ctx() -> AffordabilityContext:
    data = load_income_raw()
    return AffordabilityContext(
        income_months=[Decimal(str(m)) for m in data["months"]],
        essentials=Decimal(str(data["essentials"])),
        existing_emi=Decimal(str(data["existing_emi"])),
        savings=Decimal(str(data["savings"])),
    )


def load_estimate_raw() -> dict:  # type: ignore[type-arg]
    return _load_json("hospital_estimate.json")
