"""
Policy catalogue — the policy wordings Dhaal actually holds.

The catalogue is deliberately small and honest: it lists only documents
present in the fixtures directory whose bytes we can hash and whose
clause extractions are verified against the text. Every bundled entry is
a clearly-labelled FICTIONAL sample policy (no real insurer, product, or
UIN). If a user's policy is not here, the correct flow is document
upload — Dhaal never guesses a wording it does not hold.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from routes.fixture_data import fixtures_dir
from routes.schemas import (
    CatalogueProduct,
    CatalogueSearchResponse,
    CatalogueVersionInfo,
)

router = APIRouter(prefix="/api/catalogue", tags=["catalogue"])


@dataclass(frozen=True)
class HeldDocument:
    """A policy wording held on disk, resolvable and hash-verifiable."""

    product_id: str
    insurer: str
    product_name: str
    uin: str | None
    fictional: bool
    version: str
    effective_date: str
    sample_sum_insured: str | None
    pdf_path: Path
    clauses_path: Path
    document_name: str


@lru_cache(maxsize=1)
def _load_catalogue() -> dict:  # type: ignore[type-arg]
    path = fixtures_dir() / "policy_catalogue.json"
    if not path.exists():
        raise HTTPException(
            status_code=500, detail="Policy catalogue file not found."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _product_to_schema(product: dict) -> CatalogueProduct:  # type: ignore[type-arg]
    return CatalogueProduct(
        product_id=str(product["product_id"]),
        insurer=str(product["insurer"]),
        product_name=str(product["product_name"]),
        uin=product.get("uin"),
        fictional=bool(product.get("fictional", False)),
        versions=[
            CatalogueVersionInfo(
                version=str(v["version"]),
                effective_date=str(v["effective_date"]),
            )
            for v in product.get("versions", [])
        ],
    )


def get_product(product_id: str) -> dict | None:  # type: ignore[type-arg]
    for product in _load_catalogue().get("products", []):
        if product.get("product_id") == product_id:
            return product  # type: ignore[no-any-return]
    return None


def resolve_held_document(product_id: str, version: str) -> HeldDocument:
    """Resolve a catalogue selection to the held document files.

    Raises HTTPException 404/422 with a precise reason — a selection is
    never silently mapped to a different product or version.
    """
    product = get_product(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Policy '{product_id}' is not in the catalogue of wordings "
                "Dhaal holds. Upload your policy PDF instead."
            ),
        )
    versions = product.get("versions", [])
    match = next((v for v in versions if str(v.get("version")) == version), None)
    if match is None:
        available = ", ".join(str(v.get("version")) for v in versions)
        raise HTTPException(
            status_code=422,
            detail=(
                f"Version '{version}' of {product.get('product_name')} is not "
                f"held. Available versions: {available}. Choose one, or "
                "upload your policy PDF."
            ),
        )
    doc = match["document"]
    base = fixtures_dir()
    pdf_path = base / str(doc["pdf_file"])
    clauses_path = base / str(doc["clauses_file"])
    if not pdf_path.exists() or not clauses_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Catalogue document files are missing on the server.",
        )
    return HeldDocument(
        product_id=str(product["product_id"]),
        insurer=str(product["insurer"]),
        product_name=str(product["product_name"]),
        uin=product.get("uin"),
        fictional=bool(product.get("fictional", False)),
        version=str(match["version"]),
        effective_date=str(match["effective_date"]),
        sample_sum_insured=(
            str(match["sample_sum_insured"]) if match.get("sample_sum_insured") else None
        ),
        pdf_path=pdf_path,
        clauses_path=clauses_path,
        document_name=str(doc["document_name"]),
    )


@router.get("", response_model=CatalogueSearchResponse)
def search_catalogue(q: str = Query(default="", max_length=120)) -> CatalogueSearchResponse:
    """Search held policies by insurer, product name, or product id/UIN.

    Returns only documents actually held — an empty result means "not
    held", never "does not exist". The client must not auto-select.
    """
    catalogue = _load_catalogue()
    needle = q.strip().lower()
    results: list[CatalogueProduct] = []
    for product in catalogue.get("products", []):
        if not needle:
            results.append(_product_to_schema(product))
            continue
        haystack = " ".join(
            str(product.get(k, ""))
            for k in ("insurer", "product_name", "product_id", "uin")
        ).lower()
        if needle in haystack:
            results.append(_product_to_schema(product))
    return CatalogueSearchResponse(
        query=q,
        results=results,
        note=str(catalogue.get("note", "")),
    )


@router.get("/{product_id}", response_model=CatalogueProduct)
def get_catalogue_product(product_id: str) -> CatalogueProduct:
    product = get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Policy not in catalogue")
    return _product_to_schema(product)
