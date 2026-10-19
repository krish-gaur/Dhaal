"""Document upload and processing route."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from db.session_store import create_document, get_db, get_session, upsert_clauses
from evidence.extract import get_provider
from evidence.verify import check_injection, verify_all
from routes.schemas import DocumentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["document"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_PDF_MAGIC = b"%PDF"

# Fixture document metadata (used when session mode is "fixture")
import os

_FIXTURE_PDF_PATH = Path(
    os.getenv("DHAAL_FIXTURES_DIR")
    or str(Path(__file__).parent.parent.parent.parent / "fixtures")
) / "policy_suraksha_shield.pdf"


def _extract_page_texts(file_bytes: bytes) -> list[str]:
    """Extract text from PDF bytes using pdfplumber. Returns per-page strings."""
    import io
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber not installed")

    page_texts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_texts.append(text)
    return page_texts


def _is_scanned_pdf(page_texts: list[str]) -> bool:
    """Return True if the PDF appears to be image-only (no extractable text)."""
    total_chars = sum(len(t.strip()) for t in page_texts)
    return total_chars < 50  # fewer than 50 chars total = likely scanned


@router.post("/{session_id}/document", response_model=DocumentResponse)
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # In fixture mode: use the pre-generated fixture PDF
    if session.mode == "fixture":
        return _load_fixture_document(db, session_id)

    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 10 MB.",
        )

    # Validate PDF magic bytes
    if not file_bytes.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=422,
            detail="That file doesn't look like a PDF. Please upload a PDF file.",
        )

    # Extract text
    page_texts = _extract_page_texts(file_bytes)

    if not page_texts:
        raise HTTPException(
            status_code=422,
            detail="Could not read that PDF. Please try a different file.",
        )

    # Detect scanned PDF
    if _is_scanned_pdf(page_texts):
        raise HTTPException(
            status_code=422,
            detail=(
                "This looks like a scan. Dhaal reads text PDFs only. "
                "You can enter the figures manually."
            ),
        )

    # Injection check on all page text
    full_text = " ".join(page_texts)
    if check_injection(full_text):
        logger.warning(
            "Injection markers detected in document for session %s — quarantined",
            session_id,
        )
        raise HTTPException(
            status_code=422,
            detail=(
                "This document contains content that cannot be processed automatically. "
                "Please use manual entry."
            ),
        )

    # Store document
    doc = create_document(
        db,
        session_id=session_id,
        filename=file.filename or "policy.pdf",
        page_count=len(page_texts),
        page_texts=page_texts,
    )

    # Extract and verify clauses
    provider = get_provider()
    raw_clauses = provider.extract_clauses(page_texts, doc.id)
    verified_clauses = verify_all(raw_clauses, page_texts)

    clause_dicts = [
        {
            "clause_id": c.clause_id,
            "document_id": c.document_id,
            "page": c.page,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "quote": c.quote,
            "quote_hash": c.quote_hash,
            "rule": {"type": c.rule.type, "params": c.rule.params},
            "verification": {
                "schema_valid": c.verification.schema_valid,
                "quote_found": c.verification.quote_found,
                "numbers_supported": c.verification.numbers_supported,
                "interpretation_status": c.verification.interpretation_status.value,
                "reason": c.verification.reason,
            },
        }
        for c in verified_clauses
    ]

    upsert_clauses(db, session_id=session_id, document_id=doc.id, clauses=clause_dicts)

    return DocumentResponse(
        document_id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        mode="live",
    )


def _load_fixture_document(db: sqlite3.Connection, session_id: str) -> DocumentResponse:
    """Load the fixture PDF and clauses for a fixture-mode session."""
    if not _FIXTURE_PDF_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Fixture PDF not found. Run fixtures/generate_pdf.py first.",
        )

    # Extract text from fixture PDF
    page_texts = _extract_page_texts(_FIXTURE_PDF_PATH.read_bytes())

    doc = create_document(
        db,
        session_id=session_id,
        filename="policy_suraksha_shield.pdf",
        page_count=len(page_texts),
        page_texts=page_texts,
    )

    # Use fixture provider — no network
    from evidence.providers.fixture import FixtureProvider
    provider = FixtureProvider()
    raw_clauses = provider.extract_clauses(page_texts, doc.id)

    clause_dicts = [
        {
            "clause_id": c.clause_id,
            "document_id": doc.id,
            "page": c.page,
            "char_start": c.char_start,
            "char_end": c.char_end,
            "quote": c.quote,
            "quote_hash": c.quote_hash,
            "rule": {"type": c.rule.type, "params": c.rule.params},
            "verification": {
                "schema_valid": c.verification.schema_valid,
                "quote_found": c.verification.quote_found,
                "numbers_supported": c.verification.numbers_supported,
                "interpretation_status": c.verification.interpretation_status.value,
                "reason": c.verification.reason,
            },
        }
        for c in raw_clauses
    ]

    upsert_clauses(db, session_id=session_id, document_id=doc.id, clauses=clause_dicts)

    return DocumentResponse(
        document_id=doc.id,
        filename="Sample policy · Suraksha Shield Health (fictional)",
        page_count=len(page_texts),
        mode="fixture",
    )
