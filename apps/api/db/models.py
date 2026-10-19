"""
Database models — simple dataclasses mirroring the DB schema.
We use raw sqlite3 instead of SQLAlchemy ORM due to Python 3.14 compatibility.
The schema is defined in migrations/001_initial.sql.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SessionRow:
    id: str
    mode: str
    goal: str | None
    created_at: str
    deleted_at: str | None


@dataclass
class DocumentRow:
    id: str
    session_id: str
    filename: str
    page_count: int
    text_content: str  # JSON list of page strings
    created_at: str


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
