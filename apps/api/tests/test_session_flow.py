"""
Tests for the session-detail, document-pages, estimate, and audit endpoints,
plus the F-E11 simulation gate (confirm OR mark unknown) and the API-level
continuity counterfactual.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

_API_DIR = Path(__file__).parent.parent
_REPO_ROOT = _API_DIR.parent.parent
_FIXTURE_PDF = _REPO_ROOT / "fixtures" / "policy_suraksha_shield.pdf"

sys.path.insert(0, str(_API_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_smoke.db")
os.environ["DHAAL_FIXTURES_DIR"] = str(_REPO_ROOT / "fixtures")

from fastapi.testclient import TestClient

from db.session_store import init_db
from main import app

init_db()
client = TestClient(app)

_CHARGES = [
    {"name": "Room", "amount": "13500", "nights": 3},
    {"name": "Surgeon fees", "amount": "42000"},
    {"name": "OT charges", "amount": "18000"},
    {"name": "Medicines", "amount": "32500"},
    {"name": "Diagnostics", "amount": "14000"},
]


def _new_session_with_doc() -> str:
    r = client.post("/api/session", json={"use_fixture": True})
    session_id = str(r.json()["session_id"])
    with open(_FIXTURE_PDF, "rb") as f:
        client.post(
            f"/api/session/{session_id}/document",
            files={"file": ("policy.pdf", f, "application/pdf")},
        )
    return session_id


def _patch(session_id: str, clause_id: str, status: str) -> None:
    r = client.patch(
        f"/api/session/{session_id}/clauses/{clause_id}", json={"status": status}
    )
    assert r.status_code == 200, r.text


def _simulate_body(month: int = 25, apportionment: str = "surgeon_ot_diagnostics") -> dict:  # type: ignore[type-arg]
    return {
        "gross": "120000",
        "charges": _CHARGES,
        "room_rate_per_night": "4500",
        "nights": 3,
        "assumptions": {
            "policy_month_at_admit": month,
            "remaining_sum_insured": "300000",
            "sum_insured": "300000",
            "non_payable_total": "9500",
            "apportionment_base": apportionment,
            "continuity_confirmed": False,
        },
    }


def test_session_detail_gate_transitions() -> None:
    sid = _new_session_with_doc()
    try:
        r = client.get(f"/api/session/{sid}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["mode"] == "fixture"
        assert detail["has_document"] is True
        # Apportionment starts unverified → not ready
        assert detail["simulation_ready"] is False
        states = {f["rule_type"]: f["status"] for f in detail["material_facts"]}
        assert states["apportionment_base"] == "unverified"
        assert states["room_rent_limit"] == "verified"

        # Marking unknown also unlocks (F-E11) — with a range, not a block.
        # Crucially, readiness must not relabel the fact: it stays reported
        # as "unknown", never silently upgraded to a verified-looking state.
        _patch(sid, "c_apportionment_01", "unknown")
        detail = client.get(f"/api/session/{sid}").json()
        assert detail["simulation_ready"] is True
        states = {f["rule_type"]: f["status"] for f in detail["material_facts"]}
        assert states["apportionment_base"] == "unknown"
        assert states["room_rent_limit"] == "verified"
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_document_pages_endpoint() -> None:
    sid = _new_session_with_doc()
    try:
        r = client.get(f"/api/session/{sid}/document")
        assert r.status_code == 200
        data = r.json()
        assert data["page_count"] == 6
        assert len(data["pages"]) == 6
        # Page 4 (index 3) carries the room rent clause text
        assert "Room rent shall be limited to 1%" in data["pages"][3]
        assert "FICTIONAL" in data["pages"][0]
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_estimate_endpoint() -> None:
    sid = _new_session_with_doc()
    try:
        r = client.get(f"/api/session/{sid}/estimate")
        assert r.status_code == 200
        est = r.json()
        assert est["gross_bill"] == "120000"
        assert est["sum_insured"] == "300000"
        assert est["policy_month_at_admit"] == 19
        assert est["non_payable_total"] == "9500"
        assert est["synthetic"] is True
        # Server-derived from the verified room clause: 1% of ₹3,00,000
        assert Decimal(est["room_cap_per_day"]) == Decimal("3000")
        assert est["waiting_months_required"] == 24
        aff = est["affordability"]
        assert aff["savings"] == "35000"
        assert aff["lowest_income"] == "22500"
        assert Decimal(aff["lean_free_cash"]) == Decimal("-200")
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_gate_blocks_then_unknown_gives_range() -> None:
    sid = _new_session_with_doc()
    try:
        # Apportionment unverified → 422 gate
        r = client.post(f"/api/session/{sid}/simulate", json=_simulate_body())
        assert r.status_code == 422
        assert "apportionment base" in r.json()["detail"]

        _patch(sid, "c_apportionment_01", "unknown")
        r = client.post(
            f"/api/session/{sid}/simulate",
            json=_simulate_body(apportionment="unresolved"),
        )
        assert r.status_code == 200, r.text
        result = r.json()
        # No proportionate deduction applied at the point estimate. The
        # range is bounded by the readings the fixture clause's wording
        # supports: it defines the base as surgeon/OT/diagnostics and
        # expressly exempts medicines, so the ceiling is scenario B's
        # ₹38,667 — not the ₹49,500 an all-medical reading (which the
        # wording rules out) would give.
        assert result["insurer_payment"] == "106000"
        assert result["range_low"] == "14000"
        assert result["range_high"] == "38667"
        assert Decimal(result["range_low"]) >= 0
        assert len(result["unresolved"]) == 1
        assert result["invariants_ok"] is True
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_counterfactual_continuity_via_api() -> None:
    """The headline attribution: month 19 → 25 must yield +₹81,333."""
    sid = _new_session_with_doc()
    try:
        for cid in (
            "c_room_rent_01",
            "c_waiting_period_01",
            "c_non_payable_01",
            "c_apportionment_01",
        ):
            _patch(sid, cid, "user_confirmed")

        body = {
            "base": _simulate_body(month=19),
            "change": {"field": "policy_month_at_admit", "from_val": 19, "to_val": 25},
        }
        r = client.post(f"/api/session/{sid}/counterfactual", json=body)
        assert r.status_code == 200, r.text
        cf = r.json()
        assert Decimal(cf["delta"]) == Decimal("81333")
        assert Decimal(cf["oop_delta"]) == Decimal("-81333")
        assert cf["result"]["insurer_payment"] == "81333"
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_audit_endpoint_and_plan_derivation() -> None:
    sid = _new_session_with_doc()
    try:
        for cid in (
            "c_room_rent_01",
            "c_waiting_period_01",
            "c_non_payable_01",
            "c_apportionment_01",
        ):
            _patch(sid, cid, "user_confirmed")

        r = client.post(f"/api/session/{sid}/simulate", json=_simulate_body())
        assert r.status_code == 200, r.text

        audit = client.get(f"/api/session/{sid}/audit").json()
        assert audit["engine_version"]
        assert audit["provider_name"] == "fixture"
        assert "Nothing was sent" in audit["provider_disclosure"]
        assert audit["document"]["page_count"] == 6
        assert len(audit["runs"]) >= 1
        assert audit["runs"][0]["run_hash"].startswith("sha256:")
        assert audit["runs"][0]["insurer_payment"] == "81333"
        assert audit["clauses_by_status"].get("user_confirmed") == 4

        plan = client.get(f"/api/session/{sid}/plan").json()
        values = [s["rupee_value"] for s in plan["steps"]]
        # Derived, ranked figures: continuity, room, apportionment, loan warn
        assert values == ["81333", "29167", "24667", "0"], values
        assert "₹81,333" in plan["steps"][0]["why"]
        assert "must cover" not in plan["steps"][0]["why"]
        assert "14 days" in plan["draft_message"]
        assert "Bima Bharosa" in plan["draft_message"]
    finally:
        client.post(f"/api/session/{sid}/delete")
