"""
API smoke test — end-to-end flow through all routes.

Drives the full session flow:
1. POST /api/session (fixture mode)
2. POST /api/session/:id/document (triggers fixture document loading)
3. GET /api/session/:id/clauses (4 clauses returned)
4. PATCH clause to user_confirmed
5. POST /api/session/:id/simulate → insurer = 81333
6. POST /api/session/:id/counterfactual → delta = 29167
7. GET /api/session/:id/loans → 3 offers, all with negative lean-month
8. GET /api/session/:id/plan → 4 steps
9. POST /api/session/:id/delete → verified counts

All monetary assertions match spec §6.4 golden values.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

# Put api dir on path
_API_DIR = Path(__file__).parent.parent          # apps/api
_REPO_ROOT = _API_DIR.parent.parent             # Dhaal/
_FIXTURE_PDF = _REPO_ROOT / "fixtures" / "policy_suraksha_shield.pdf"

sys.path.insert(0, str(_API_DIR))

# Use a test DB so tests don't touch the dev DB
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_smoke.db")

# Set fixture path explicitly — avoids __file__ path resolution ambiguity
_DHAAL_ROOT = Path(__file__).parent.parent.parent.parent
os.environ["DHAAL_FIXTURES_DIR"] = str(_DHAAL_ROOT / "fixtures")

from fastapi.testclient import TestClient

from db.session_store import init_db
from main import app

init_db()

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _d(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Full flow test
# ---------------------------------------------------------------------------


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_fixture_flow() -> None:
    # Step 1 — create session
    r = client.post("/api/session", json={"use_fixture": True, "goal": "gallbladder surgery"})
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "fixture"
    session_id = data["session_id"]
    assert len(session_id) == 36  # UUID

    # Step 2 — load fixture document
    # POST with an empty file body; fixture mode ignores the file
    fixture_pdf = _FIXTURE_PDF
    with open(fixture_pdf, "rb") as f:
        r = client.post(
            f"/api/session/{session_id}/document",
            files={"file": ("policy.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200
    doc_data = r.json()
    assert doc_data["page_count"] == 6
    assert "fictional" in doc_data["filename"].lower() or "suraksha" in doc_data["filename"].lower()

    # Step 3 — list clauses
    r = client.get(f"/api/session/{session_id}/clauses")
    assert r.status_code == 200
    clauses = r.json()
    assert len(clauses) == 4
    clause_ids = {c["clause_id"] for c in clauses}
    assert "c_room_rent_01" in clause_ids
    assert "c_waiting_period_01" in clause_ids
    assert "c_non_payable_01" in clause_ids
    assert "c_apportionment_01" in clause_ids

    # Step 4 — confirm all material clauses
    for clause in clauses:
        cid = clause["clause_id"]
        r = client.patch(
            f"/api/session/{session_id}/clauses/{cid}",
            json={"status": "user_confirmed"},
        )
        assert r.status_code == 200
        assert r.json()["verification"]["interpretation_status"] == "user_confirmed"

    # Step 5 — simulate scenario B (continuity confirmed, room above cap)
    simulate_body = {
        "gross": "120000",
        "charges": [
            {"name": "Room", "amount": "13500", "nights": 3},
            {"name": "Surgeon fees", "amount": "42000"},
            {"name": "OT charges", "amount": "18000"},
            {"name": "Medicines", "amount": "32500"},
            {"name": "Diagnostics", "amount": "14000"},
        ],
        "room_rate_per_night": "4500",
        "nights": 3,
        "assumptions": {
            "policy_month_at_admit": 25,
            "remaining_sum_insured": "300000",
            "sum_insured": "300000",
            "non_payable_total": "9500",
            "apportionment_base": "surgeon_ot_diagnostics",
            "continuity_confirmed": True,
        },
    }
    r = client.post(f"/api/session/{session_id}/simulate", json=simulate_body)
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["invariants_ok"] is True
    assert result["insurer_payment"] == "81333"
    assert result["out_of_pocket"] == "38667"
    assert result["gross_bill"] == "120000"
    # Conservation
    assert _d(result["insurer_payment"]) + _d(result["out_of_pocket"]) == _d(result["gross_bill"])

    # Step 6 — counterfactual: move room to cap
    # Change room_rate_per_night from 4500 to 3000
    cf_body = {
        "base": simulate_body,
        "change": {
            "field": "room_rate_per_night",
            "from_val": "4500",
            "to_val": "3000",
        },
    }
    r = client.post(f"/api/session/{session_id}/counterfactual", json=cf_body)
    assert r.status_code == 200, r.text
    cf = r.json()
    # delta = new insurer - base insurer = 110500 - 81333 = 29167
    assert _d(cf["delta"]) == _d("29167")
    assert cf["changed_fields"] == ["room_rate_per_night"]

    # Step 7 — loans
    r = client.get(f"/api/session/{session_id}/loans")
    assert r.status_code == 200
    loans = r.json()
    assert len(loans) == 3
    labels = {lo["label"] for lo in loans}
    assert labels == {"A", "B", "C"}

    # All three must have negative lean-month free cash
    for loan in loans:
        assert _d(loan["free_cash_lean_month"]) < _d("0"), (
            f"Offer {loan['label']} lean free cash should be negative: "
            f"{loan['free_cash_lean_month']}"
        )

    # APR is present and labelled
    for loan in loans:
        assert _d(loan["apr_nominal"]) > _d("0")
        assert _d(loan["apr_effective"]) > _d("0")
        assert loan["synthetic"] is True

    # Step 8 — plan
    r = client.get(f"/api/session/{session_id}/plan")
    assert r.status_code == 200
    plan = r.json()
    assert len(plan["steps"]) == 4
    assert plan["steps"][0]["rank"] == 1
    assert "81,333" in plan["steps"][0]["why"] or "81333" in plan["steps"][0]["why"]
    assert "draft_message" in plan
    assert "GRO" in plan["draft_message"] or "Grievance" in plan["draft_message"]

    # Step 9 — delete
    r = client.post(f"/api/session/{session_id}/delete")
    assert r.status_code == 200
    del_data = r.json()
    assert del_data["deleted"] is True
    assert del_data["verified"] is True
    assert del_data["counts"]["documents"] >= 1
    assert del_data["counts"]["clauses"] >= 4
    assert del_data["counts"]["runs"] >= 1

    # Verify session is gone
    r = client.get(f"/api/session/{session_id}/clauses")
    assert r.status_code == 404


def test_simulate_scenario_a_waiting_period() -> None:
    """Scenario A: waiting period not met → insurer = 0."""
    r = client.post("/api/session", json={"use_fixture": True})
    session_id = r.json()["session_id"]

    fixture_pdf = _FIXTURE_PDF
    with open(fixture_pdf, "rb") as f:
        client.post(f"/api/session/{session_id}/document",
                    files={"file": ("p.pdf", f, "application/pdf")})

    # Confirm clauses
    clauses = client.get(f"/api/session/{session_id}/clauses").json()
    for c in clauses:
        client.patch(f"/api/session/{session_id}/clauses/{c['clause_id']}",
                     json={"status": "user_confirmed"})

    # Simulate with month 19 (< 24 required) and continuity_confirmed=False
    r = client.post(f"/api/session/{session_id}/simulate", json={
        "gross": "120000",
        "charges": [
            {"name": "Room", "amount": "13500", "nights": 3},
            {"name": "Surgeon fees", "amount": "42000"},
            {"name": "OT charges", "amount": "18000"},
            {"name": "Medicines", "amount": "32500"},
            {"name": "Diagnostics", "amount": "14000"},
        ],
        "room_rate_per_night": "4500",
        "nights": 3,
        "assumptions": {
            "policy_month_at_admit": 19,
            "remaining_sum_insured": "300000",
            "sum_insured": "300000",
            "non_payable_total": "9500",
            "apportionment_base": "surgeon_ot_diagnostics",
            "continuity_confirmed": False,
        },
    })
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["insurer_payment"] == "0"
    assert result["out_of_pocket"] == "120000"
    assert result["invariants_ok"] is True

    client.post(f"/api/session/{session_id}/delete")


def test_simulate_scenario_c1() -> None:
    """Scenario C1: room at cap → insurer = 110500, oop = 9500."""
    r = client.post("/api/session", json={"use_fixture": True})
    session_id = r.json()["session_id"]

    fixture_pdf = _FIXTURE_PDF
    with open(fixture_pdf, "rb") as f:
        client.post(f"/api/session/{session_id}/document",
                    files={"file": ("p.pdf", f, "application/pdf")})

    clauses = client.get(f"/api/session/{session_id}/clauses").json()
    for c in clauses:
        client.patch(f"/api/session/{session_id}/clauses/{c['clause_id']}",
                     json={"status": "user_confirmed"})

    r = client.post(f"/api/session/{session_id}/simulate", json={
        "gross": "120000",
        "charges": [
            {"name": "Room", "amount": "9000", "nights": 3},
            {"name": "Surgeon fees", "amount": "46500"},
            {"name": "OT charges", "amount": "18000"},
            {"name": "Medicines", "amount": "32500"},
            {"name": "Diagnostics", "amount": "14000"},
        ],
        "room_rate_per_night": "3000",
        "nights": 3,
        "assumptions": {
            "policy_month_at_admit": 25,
            "remaining_sum_insured": "300000",
            "sum_insured": "300000",
            "non_payable_total": "9500",
            "apportionment_base": "surgeon_ot_diagnostics",
            "continuity_confirmed": True,
        },
    })
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["insurer_payment"] == "110500"
    assert result["out_of_pocket"] == "9500"
    assert _d(result["insurer_payment"]) + _d(result["out_of_pocket"]) == _d(result["gross_bill"])

    client.post(f"/api/session/{session_id}/delete")


def test_scanned_pdf_rejected() -> None:
    """A PDF with no extractable text returns 422 with correct message."""
    r = client.post("/api/session", json={"use_fixture": False})
    session_id = r.json()["session_id"]

    # Create a minimal valid PDF with no text content
    minimal_pdf = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )
    r = client.post(
        f"/api/session/{session_id}/document",
        files={"file": ("scan.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 422
    assert "scan" in r.json()["detail"].lower() or "text" in r.json()["detail"].lower()

    client.post(f"/api/session/{session_id}/delete")
