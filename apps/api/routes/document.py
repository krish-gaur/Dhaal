"""Document upload and processing route.

Policy-first: a fixture-mode session loads the EXACT held wording the
user selected from the catalogue (product + version pinned at session
creation), and every document carries provenance — source kind, version,
effective date, SHA-256 and retrieval time — so a calculation can always
be tied to the bytes it came from.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from db.models import DocumentRow, SessionRow
from db.session_store import (
    create_document,
    get_db,
    get_document,
    get_session,
    upsert_clauses,
)
from evidence.extract import get_provider
from evidence.verify import check_injection, verify_all
from routes.catalogue import HeldDocument, resolve_held_document
from routes.schemas import (
    DocumentPagesResponse,
    DocumentProvenance,
    DocumentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/session", tags=["document"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_PDF_MAGIC = b"%PDF"


def _extract_page_texts(file_bytes: bytes) -> list[str]:
    """Extract text from PDF bytes using pdfplumber. Returns per-page strings."""
    import io
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(status_code=500, detail="pdfplumber not installed") from None

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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _provenance_response(doc: DocumentRow) -> DocumentProvenance:
    return DocumentProvenance(
        source_kind=doc.source_kind or "user_upload",
        source_url=doc.source_url,
        doc_version=doc.doc_version,
        effective_date=doc.effective_date,
        uin=doc.uin,
        sha256=doc.sha256,
        retrieved_at=doc.retrieved_at,
    )


@router.post("/{session_id}/document", response_model=DocumentResponse)
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # In fixture mode: load the exact catalogue wording the user selected.
    if session.mode == "fixture":
        return _load_fixture_document(db, session)

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
    try:
        page_texts = _extract_page_texts(file_bytes)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=422,
            detail="Could not read that PDF. Please try a different file.",
        ) from None

    if not page_texts:
        raise HTTPException(
            status_code=422,
            detail="Could not read that PDF. Please try a different file.",
        )

    # Page count must be within a sane range for a policy document
    if len(page_texts) > 100:
        raise HTTPException(
            status_code=422,
            detail="That PDF has more than 100 pages. Please upload the policy wording only.",
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

    # Store document with upload provenance
    doc = create_document(
        db,
        session_id=session_id,
        filename=file.filename or "policy.pdf",
        page_count=len(page_texts),
        page_texts=page_texts,
        source_kind="user_upload",
        sha256=hashlib.sha256(file_bytes).hexdigest(),
        retrieved_at=_now_iso(),
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
        provenance=_provenance_response(doc),
    )


def _held_document_for(session: SessionRow) -> HeldDocument:
    """Resolve the held wording pinned to this session.

    Legacy fixture sessions (created before catalogue identity existed)
    fall back to the historical sample policy — the document they were
    always meant to load.
    """
    product_id = session.catalogue_product_id or "suraksha-shield-health"
    version = session.catalogue_version or "2022"
    return resolve_held_document(product_id, version)


def _load_fixture_document(db: sqlite3.Connection, session: SessionRow) -> DocumentResponse:
    """Load the selected catalogue wording and its verified clauses."""
    held = _held_document_for(session)
    pdf_bytes = held.pdf_path.read_bytes()
    page_texts = _extract_page_texts(pdf_bytes)

    both_names = (
        f"{held.insurer} {held.product_name}".strip()
        if held.product_name not in held.insurer
        else held.insurer
    )
    display_name = f"{both_names} · {held.version} wording (fictional sample)"

    doc = create_document(
        db,
        session_id=session.id,
        filename=display_name,
        page_count=len(page_texts),
        page_texts=page_texts,
        source_kind="catalogue_document",
        doc_version=held.version,
        effective_date=held.effective_date,
        uin=held.uin,
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        retrieved_at=_now_iso(),
    )

    # Held clauses only — no network, no invention. The clause file is the
    # one the catalogue entry names for this exact product + version.
    from evidence.providers.fixture import FixtureProvider

    provider = FixtureProvider()
    raw_clauses = provider.extract_clauses(
        page_texts, doc.id, clauses_path=held.clauses_path
    )

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

    upsert_clauses(db, session_id=session.id, document_id=doc.id, clauses=clause_dicts)

    return DocumentResponse(
        document_id=doc.id,
        filename=display_name,
        page_count=len(page_texts),
        mode="fixture",
        provenance=_provenance_response(doc),
    )


@router.get("/{session_id}/document", response_model=DocumentPagesResponse)
def get_document_pages(
    session_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentPagesResponse:
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    doc = get_document(db, session_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No document in this session")
    try:
        pages_raw = json.loads(doc.text_content)
        pages = [str(p) for p in pages_raw] if isinstance(pages_raw, list) else []
    except Exception:
        pages = []
    return DocumentPagesResponse(
        document_id=doc.id,
        filename=doc.filename,
        page_count=doc.page_count,
        pages=pages,
        provenance=_provenance_response(doc),
    )
