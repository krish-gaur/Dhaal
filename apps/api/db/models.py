"""
Database models — simple dataclasses mirroring the DB schema.
We use raw sqlite3 instead of SQLAlchemy ORM due to Python 3.14 compatibility.
The schema is defined in migrations/001_initial.sql.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionRow:
    id: str
    mode: str
    goal: str | None
    created_at: str
    deleted_at: str | None
    # Policy identification (002). identification_status is one of
    # "catalogue_verified" (document held by Dhaal and hash-checked),
    # "user_declared" (user named a policy we do not hold; document is
    # their upload), or None/"unidentified".
    catalogue_product_id: str | None = None
    catalogue_version: str | None = None
    insurer_name: str | None = None
    product_name: str | None = None
    identification_status: str | None = None


@dataclass
class DocumentRow:
    id: str
    session_id: str
    filename: str
    page_count: int
    text_content: str  # JSON list of page strings
    created_at: str
    # Provenance (002): where this document came from and how to verify it.
    source_kind: str | None = None  # "catalogue" | "user_upload"
    source_url: str | None = None
    doc_version: str | None = None
    effective_date: str | None = None
    uin: str | None = None
    sha256: str | None = None
    retrieved_at: str | None = None


@dataclass
class ClauseRow:
    id: str
    document_id: str
    session_id: str
    page: int | None
    char_start: int | None
    char_end: int | None
    quote: str | None
    quote_hash: str | None
    rule_type: str | None
    rule_params: str | None  # JSON
    status: str
    reason: str | None
    schema_valid: int | None  # SQLite stores booleans as int
    quote_found: int | None
    numbers_ok: int | None
    created_at: str


@dataclass
class SimulationRunRow:
    id: str
    session_id: str
    inputs_json: str
    result_json: str
    invariants_ok: int
    created_at: str
