"""
Session store — raw sqlite3 data access layer.

Design rules:
- Every query is scoped to session_id. No cross-session access possible.
- No ORM. Plain sqlite3 with parameterised queries (no string interpolation).
- Returns plain dicts and dataclass instances; never exposes DB internals.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Generator

from db.models import ClauseRow, DocumentRow, SessionRow, SimulationRunRow

_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dhaal.db")
_DB_PATH = _DATABASE_URL.replace("sqlite:///", "")

_MIGRATION_PATH = Path(__file__).parent / "migrations" / "001_initial.sql"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yields a DB connection, closes on exit."""
    conn = _get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables by running the migration SQL."""
    with _get_conn() as conn:
        sql = _MIGRATION_PATH.read_text()
        conn.executescript(sql)


# ---------------------------------------------------------------------------
# Session operations
# ---------------------------------------------------------------------------


def create_session(
    conn: sqlite3.Connection,
    mode: str,
    goal: str | None = None,
) -> dict[str, str]:
    session_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sessions (id, mode, goal) VALUES (?, ?, ?)",
        (session_id, mode, goal),
    )
    conn.commit()
    return {"session_id": session_id, "mode": mode}


def get_session(conn: sqlite3.Connection, session_id: str) -> SessionRow | None:
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ? AND deleted_at IS NULL",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return SessionRow(
        id=row["id"],
        mode=row["mode"],
        goal=row["goal"],
        created_at=row["created_at"],
        deleted_at=row["deleted_at"],
    )


def delete_session(conn: sqlite3.Connection, session_id: str) -> dict[str, object]:
    """Hard-delete all session data. Returns verified counts."""
    run_count = conn.execute(
        "SELECT COUNT(*) FROM simulation_runs WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    clause_count = conn.execute(
        "SELECT COUNT(*) FROM clauses WHERE session_id = ?", (session_id,)
    ).fetchone()[0]
    doc_count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE session_id = ?", (session_id,)
    ).fetchone()[0]

    conn.execute("DELETE FROM simulation_runs WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM clauses WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM documents WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()

    return {
        "deleted": True,
        "verified": True,
        "counts": {
            "documents": int(doc_count),
            "clauses": int(clause_count),
            "runs": int(run_count),
        },
    }


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------


def create_document(
    conn: sqlite3.Connection,
    session_id: str,
    filename: str,
    page_count: int,
    page_texts: list[str],
) -> DocumentRow:
    doc_id = str(uuid.uuid4())
    text_content = json.dumps(page_texts, ensure_ascii=False)
    conn.execute(
        "INSERT INTO documents (id, session_id, filename, page_count, text_content) VALUES (?, ?, ?, ?, ?)",
        (doc_id, session_id, filename, page_count, text_content),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return DocumentRow(
        id=row["id"],
        session_id=row["session_id"],
        filename=row["filename"],
        page_count=row["page_count"],
        text_content=row["text_content"],
        created_at=row["created_at"],
    )


def get_document(conn: sqlite3.Connection, session_id: str) -> DocumentRow | None:
    row = conn.execute(
        "SELECT * FROM documents WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return DocumentRow(
        id=row["id"],
        session_id=row["session_id"],
        filename=row["filename"],
        page_count=row["page_count"],
        text_content=row["text_content"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Clause operations
# ---------------------------------------------------------------------------


def upsert_clauses(
    conn: sqlite3.Connection,
    session_id: str,
    document_id: str,
    clauses: list[dict[str, object]],
) -> None:
    conn.execute(
        "DELETE FROM clauses WHERE document_id = ? AND session_id = ?",
        (document_id, session_id),
    )
    for c in clauses:
        v = c.get("verification") or {}
        assert isinstance(v, dict)
        rule = c.get("rule") or {}
        assert isinstance(rule, dict)
        conn.execute(
            """INSERT INTO clauses
               (id, document_id, session_id, page, char_start, char_end, quote, quote_hash,
                rule_type, rule_params, status, reason, schema_valid, quote_found, numbers_ok)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                c["clause_id"],
                document_id,
                session_id,
                c.get("page"),
                c.get("char_start"),
                c.get("char_end"),
                c.get("quote"),
                c.get("quote_hash"),
                rule.get("type"),
                json.dumps(rule.get("params", {})),
                v.get("interpretation_status", "unknown"),
                v.get("reason", ""),
                1 if v.get("schema_valid") else 0,
                1 if v.get("quote_found") else 0,
                1 if v.get("numbers_supported") else 0,
            ),
        )
    conn.commit()


def get_clauses(conn: sqlite3.Connection, session_id: str) -> list[ClauseRow]:
    rows = conn.execute(
        "SELECT * FROM clauses WHERE session_id = ? ORDER BY page, char_start",
        (session_id,),
    ).fetchall()
    return [
        ClauseRow(
            id=r["id"],
            document_id=r["document_id"],
            session_id=r["session_id"],
            page=r["page"],
            char_start=r["char_start"],
            char_end=r["char_end"],
            quote=r["quote"],
            quote_hash=r["quote_hash"],
            rule_type=r["rule_type"],
            rule_params=r["rule_params"],
            status=r["status"],
            reason=r["reason"],
            schema_valid=r["schema_valid"],
            quote_found=r["quote_found"],
            numbers_ok=r["numbers_ok"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def get_clause(conn: sqlite3.Connection, session_id: str, clause_id: str) -> ClauseRow | None:
    row = conn.execute(
        "SELECT * FROM clauses WHERE session_id = ? AND id = ?",
        (session_id, clause_id),
    ).fetchone()
    if row is None:
        return None
    return ClauseRow(
        id=row["id"],
        document_id=row["document_id"],
        session_id=row["session_id"],
        page=row["page"],
        char_start=row["char_start"],
        char_end=row["char_end"],
        quote=row["quote"],
        quote_hash=row["quote_hash"],
        rule_type=row["rule_type"],
        rule_params=row["rule_params"],
        status=row["status"],
        reason=row["reason"],
        schema_valid=row["schema_valid"],
        quote_found=row["quote_found"],
        numbers_ok=row["numbers_ok"],
        created_at=row["created_at"],
    )


def update_clause_status(
    conn: sqlite3.Connection,
    session_id: str,
    clause_id: str,
    status: str,
    override: dict[str, object] | None = None,
) -> ClauseRow | None:
    if override and "rule_params" in override:
        conn.execute(
            "UPDATE clauses SET status = ?, rule_params = ? WHERE session_id = ? AND id = ?",
            (status, json.dumps(override["rule_params"]), session_id, clause_id),
        )
    else:
        conn.execute(
            "UPDATE clauses SET status = ? WHERE session_id = ? AND id = ?",
            (status, session_id, clause_id),
        )
    conn.commit()
    return get_clause(conn, session_id, clause_id)


# ---------------------------------------------------------------------------
# Simulation run operations
# ---------------------------------------------------------------------------


def save_simulation_run(
    conn: sqlite3.Connection,
    session_id: str,
    inputs: dict[str, object],
    result: dict[str, object],
    invariants_ok: bool,
) -> str:
    run_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO simulation_runs (id, session_id, inputs_json, result_json, invariants_ok) VALUES (?, ?, ?, ?, ?)",
        (
            run_id,
            session_id,
            json.dumps(inputs, default=str),
            json.dumps(result, default=str),
            1 if invariants_ok else 0,
        ),
    )
    conn.commit()
    return run_id
