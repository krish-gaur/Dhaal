"""
Policy-first tests: catalogue identification, exact-version resolution,
document provenance, policy-specific rule extraction, scoped waiting
periods, exclusions, conflicts, and deduction traceability.

Acceptance criterion: the SAME hospital bill run against DIFFERENT held
policies (and different versions of one policy) must produce different,
hand-verifiable results driven only by each wording's own clauses.

Hand checks (bill ₹1,20,000; charges Room 13,500 / Surgeon 42,000 /
OT 18,000 / Medicines 32,500 / Diagnostics 14,000; non-payables 9,500;
room ₹4,500/night × 3; waiting periods served):
- Suraksha Shield 2022 (cap 1% of SI 3,00,000 = 3,000/day; ratio 2/3):
  insurer 81,333.
- Suraksha Shield 2024 (fixed cap 4,000/day; excess 1,500; ratio 8/9;
  proportionate cut 74,000 × 1/9 = 8,222.22): 110,500 − 1,500 − 8,222.22
  = 100,777.78 → insurer 100,777.
- AarogyaKavach Prime (fixed cap 5,000/day → no excess; 10% co-payment
  11,050; deductible 5,000): insurer 94,450.
"""

from __future__ import annotations

import hashlib
import json
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

from db.models import ClauseRow
from db.session_store import init_db
from main import app
from routes.schemas import SimulationAssumptions
from routes.simulate import _build_policy_rules

init_db()
client = TestClient(app)

_CHARGES = [
    {"name": "Room", "amount": "13500", "nights": 3},
    {"name": "Surgeon fees", "amount": "42000"},
    {"name": "OT charges", "amount": "18000"},
    {"name": "Medicines", "amount": "32500"},
    {"name": "Diagnostics", "amount": "14000"},
]


def _session(product: str | None = None, version: str | None = None) -> str:
    body: dict[str, object] = (
        {"catalogue_product_id": product, "catalogue_version": version}
        if product
        else {"use_fixture": True}
    )
    r = client.post("/api/session", json=body)
    assert r.status_code == 200, r.text
    session_id = str(r.json()["session_id"])
    with open(_FIXTURE_PDF, "rb") as f:
        r = client.post(
            f"/api/session/{session_id}/document",
            files={"file": ("policy.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200, r.text
    return session_id


def _confirm_all(session_id: str) -> list[dict]:  # type: ignore[type-arg]
    clauses: list[dict] = client.get(  # type: ignore[type-arg]
        f"/api/session/{session_id}/clauses"
    ).json()
    for c in clauses:
        client.patch(
            f"/api/session/{session_id}/clauses/{c['clause_id']}",
            json={"status": "user_confirmed"},
        )
    return clauses


def _simulate(
    session_id: str,
    *,
    si: str = "300000",
    admission: str = "2024-08-15",  # 25 months after 2022-07-15
    condition: str | None = "gallbladder_cholecystectomy",
    ped: bool = False,
    accident: bool = False,
    inception: str = "2022-07-15",
) -> dict:  # type: ignore[type-arg]
    body = {
        "gross": "120000",
        "charges": _CHARGES,
        "room_rate_per_night": "4500",
        "nights": 3,
        "assumptions": {
            "policy_month_at_admit": 25,
            "remaining_sum_insured": si,
            "sum_insured": si,
            "non_payable_total": "9500",
            "apportionment_base": "surgeon_ot_diagnostics",
            "continuity_confirmed": False,
            "condition_tag": condition,
            "is_pre_existing": ped,
            "is_accident": accident,
            "inception_date": inception,
            "admission_date": admission,
            "continuity_credit_months": 0,
        },
    }
    r = client.post(f"/api/session/{session_id}/simulate", json=body)
    assert r.status_code == 200, r.text
    result: dict = r.json()  # type: ignore[type-arg]
    return result


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


def test_catalogue_search_and_detail() -> None:
    r = client.get("/api/catalogue", params={"q": "suraksha"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert [p["product_id"] for p in results] == ["suraksha-shield-health"]
    assert results[0]["fictional"] is True
    assert {v["version"] for v in results[0]["versions"]} == {"2022", "2024"}
    # Honesty note about held documents must be present.
    assert "actually holds" in r.json()["note"]

    # Blank query lists the entire (held-only) catalogue.
    all_ids = {
        p["product_id"] for p in client.get("/api/catalogue").json()["results"]
    }
    assert all_ids == {"suraksha-shield-health", "aarogyakavach-prime"}

    # No match → empty results, not an error and never a substitute.
    assert client.get("/api/catalogue", params={"q": "zzz-nonexistent"}).json()[
        "results"
    ] == []

    detail = client.get("/api/catalogue/aarogyakavach-prime").json()
    assert detail["versions"][0]["version"] == "2022"
    assert client.get("/api/catalogue/unknown-product").status_code == 404


def test_unknown_product_session_rejected() -> None:
    r = client.post(
        "/api/session",
        json={"catalogue_product_id": "real-insurer-plan", "catalogue_version": "2023"},
    )
    assert r.status_code == 404
    assert "not in the catalogue" in r.json()["detail"]


def test_ambiguous_version_requires_user_choice() -> None:
    # Suraksha has two held versions — the server must not silently pick.
    r = client.post(
        "/api/session", json={"catalogue_product_id": "suraksha-shield-health"}
    )
    assert r.status_code == 422
    assert "multiple held versions" in r.json()["detail"]


def test_live_declared_identity_not_verified() -> None:
    r = client.post(
        "/api/session",
        json={
            "use_fixture": False,
            "declared_insurer": "Some Insurer",
            "declared_product": "Some Plan",
        },
    )
    assert r.status_code == 200, r.text
    policy = r.json()["policy"]
    assert policy["insurer"] == "Some Insurer"
    assert policy["identification_status"] == "user_declared"
    client.post(f"/api/session/{r.json()['session_id']}/delete")


# ---------------------------------------------------------------------------
# Provenance + exact wording
# ---------------------------------------------------------------------------


def test_selected_version_document_and_provenance() -> None:
    sid = _session("suraksha-shield-health", "2024")
    try:
        doc = client.get(f"/api/session/{sid}/document").json()
        assert "2024 wording" in doc["filename"]
        prov = doc["provenance"]
        assert prov["source_kind"] == "catalogue_document"
        assert prov["doc_version"] == "2024"
        assert prov["effective_date"] == "2024-04-01"
        expected_sha = hashlib.sha256(
            (_REPO_ROOT / "fixtures" / "policy_suraksha_shield_2024.pdf").read_bytes()
        ).hexdigest()
        assert prov["sha256"] == expected_sha
        assert prov["retrieved_at"]

        detail = client.get(f"/api/session/{sid}").json()
        assert detail["policy"]["product_id"] == "suraksha-shield-health"
        assert detail["policy"]["version"] == "2024"
        assert detail["policy"]["identification_status"] == "catalogue_verified"
        assert detail["policy"]["fictional"] is True
    finally:
        client.post(f"/api/session/{sid}/delete")


# ---------------------------------------------------------------------------
# Acceptance: same bill, different policies/versions → different results
# ---------------------------------------------------------------------------


def test_three_policies_three_results_same_bill() -> None:
    s22 = _session("suraksha-shield-health", "2022")
    s24 = _session("suraksha-shield-health", "2024")
    ak = _session("aarogyakavach-prime", "2022")
    try:
        _confirm_all(s22)
        _confirm_all(s24)
        _confirm_all(ak)
        r22 = _simulate(s22)
        r24 = _simulate(s24)
        rak = _simulate(ak, si="500000")
        assert r22["insurer_payment"] == "81333"
        assert r24["insurer_payment"] == "100777"
        assert rak["insurer_payment"] == "94450"
        # Deduction shapes differ by wording: only Aarogya has co-pay/deductible.
        ak_rules = {d["rule_id"] for d in rak["deductions"]}
        assert "co_payment" in ak_rules and "deductible" in ak_rules
        assert "room_rent_limit" not in ak_rules  # 4,500 < 5,000 cap
        s22_rules = {d["rule_id"] for d in r22["deductions"]}
        assert "co_payment" not in s22_rules and "deductible" not in s22_rules
    finally:
        for sid in (s22, s24, ak):
            client.post(f"/api/session/{sid}/delete")


def test_every_deduction_traces_to_a_clause() -> None:
    sid = _session("aarogyakavach-prime", "2022")
    try:
        clauses = _confirm_all(sid)
        clause_ids = {c["clause_id"] for c in clauses}
        result = _simulate(sid, si="500000")
        assert result["deductions"], "expected deductions"
        for d in result["deductions"]:
            assert d["citation"], f"deduction {d['rule_id']} has no citation"
            assert d["source_clause_id"] in clause_ids, d
            assert "§" in d["citation"] and "page" in d["citation"]
    finally:
        client.post(f"/api/session/{sid}/delete")


# ---------------------------------------------------------------------------
# Waiting periods: condition-scoped, never blanket-applied
# ---------------------------------------------------------------------------


def test_specified_waiting_only_for_listed_conditions() -> None:
    suraksha = _session("suraksha-shield-health", "2022")
    aarogya = _session("aarogyakavach-prime", "2022")
    try:
        _confirm_all(suraksha)
        _confirm_all(aarogya)
        # Month 19: gallbladder is on Suraksha's specified list → 0.
        blocked = _simulate(suraksha, admission="2024-02-15")
        assert blocked["insurer_payment"] == "0"
        [waiting_ded] = [d for d in blocked["deductions"] if d["rule_id"] == "waiting_period"]
        assert waiting_ded["source_clause_id"] == "c_waiting_period_01"
        # Same condition, same month, Aarogya does NOT list it → pays.
        paid = _simulate(aarogya, si="500000", admission="2024-02-15")
        assert paid["insurer_payment"] == "94450"
        # Unlisted condition under Suraksha at month 19 → not blocked.
        other = _simulate(
            suraksha, admission="2024-02-15", condition="appendicitis_surgery"
        )
        assert other["insurer_payment"] == "81333"
    finally:
        client.post(f"/api/session/{suraksha}/delete")
        client.post(f"/api/session/{aarogya}/delete")


def test_waiting_boundary_months() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        # 23 whole months (admission day before inception day) → blocked.
        assert _simulate(sid, admission="2024-07-14")["insurer_payment"] == "0"
        # Exactly 24 whole months → served.
        assert _simulate(sid, admission="2024-07-15")["insurer_payment"] == "81333"
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_initial_waiting_days_and_accident_exception() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        # Day 19 of cover, listed condition → initial wait blocks.
        early = _simulate(
            sid, inception="2024-01-01", admission="2024-01-20"
        )
        assert early["insurer_payment"] == "0"
        # Same dates but an accident → the clause's exception applies.
        # (Unlisted condition so the specified period cannot apply either.)
        accident = _simulate(
            sid,
            inception="2024-01-01",
            admission="2024-01-20",
            condition="fracture_treatment",
            accident=True,
        )
        assert Decimal(accident["insurer_payment"]) > 0
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_ped_waiting_only_when_pre_existing() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        # Month 25: specified served, but PED (36) blocks pre-existing claims.
        assert _simulate(sid, ped=True)["insurer_payment"] == "0"
        assert _simulate(sid, ped=False)["insurer_payment"] == "81333"
        # Month 37: PED served too.
        assert (
            _simulate(sid, ped=True, admission="2025-08-15")["insurer_payment"]
            == "81333"
        )
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_missing_claim_context_never_applies_waiting_silently() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        # No condition tag and no dates: scoped periods cannot be evaluated.
        body = {
            "gross": "120000",
            "charges": _CHARGES,
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
        }
        r = client.post(f"/api/session/{sid}/simulate", json=body)
        assert r.status_code == 200, r.text
        result = r.json()
        # Not zeroed by a guessed waiting period…
        assert Decimal(result["insurer_payment"]) > 0
        # …but surfaced as unresolved, and the range admits the worst case.
        assert any(
            u["rule_type"] == "waiting_period" for u in result["unresolved"]
        ), result["unresolved"]
        assert Decimal(result["range_high"]) == Decimal("120000")
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_unknown_waiting_clause_is_unresolved_not_applied() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        client.patch(
            f"/api/session/{sid}/clauses/c_waiting_period_01",
            json={"status": "unknown"},
        )
        result = _simulate(sid, admission="2024-02-15")  # month 19
        assert Decimal(result["insurer_payment"]) > 0
        assert any(
            u["rule_type"] == "waiting_period" for u in result["unresolved"]
        )
    finally:
        client.post(f"/api/session/{sid}/delete")


def test_permanent_exclusion_zeroes_claim() -> None:
    sid = _session("suraksha-shield-health", "2022")
    try:
        _confirm_all(sid)
        result = _simulate(sid, condition="cosmetic_treatment")
        assert result["insurer_payment"] == "0"
        [excl] = [d for d in result["deductions"] if d["rule_id"] == "exclusion"]
        assert excl["source_clause_id"] == "c_exclusion_01"
        # No double-counting: the exclusion is the only deduction.
        assert len(result["deductions"]) == 1
    finally:
        client.post(f"/api/session/{sid}/delete")


# ---------------------------------------------------------------------------
# Conflicting clauses — builder unit tests
# ---------------------------------------------------------------------------


def _clause_row(
    clause_id: str, rule_type: str, params: dict[str, str], quote: str
) -> ClauseRow:
    return ClauseRow(
        id=clause_id,
        document_id="doc_test",
        session_id="s_test",
        page=1,
        char_start=0,
        char_end=len(quote),
        quote=quote,
        quote_hash="x",
        rule_type=rule_type,
        rule_params=json.dumps(params),
        status="verified",
        reason="",
        schema_valid=1,
        quote_found=1,
        numbers_ok=1,
        created_at="2026-01-01",
    )


_ASSUMPTIONS = SimulationAssumptions(
    policy_month_at_admit=25,
    remaining_sum_insured="300000",
    sum_insured="300000",
    non_payable_total="9500",
    apportionment_base="surgeon_ot_diagnostics",
    continuity_confirmed=False,
)


def test_conflicting_room_clauses_require_review() -> None:
    clauses = [
        _clause_row(
            "c1",
            "room_rent_limit",
            {"basis": "fixed_per_day", "value": "3000"},
            "Room rent is limited to Rs. 3,000 per day.",
        ),
        _clause_row(
            "c2",
            "room_rent_limit",
            {"basis": "fixed_per_day", "value": "4000"},
            "Room rent is limited to Rs. 4,000 per day.",
        ),
    ]
    try:
        _build_policy_rules(clauses, _ASSUMPTIONS)
        raise AssertionError("expected ValueError for conflicting clauses")
    except ValueError as exc:
        assert "human review required" in str(exc)


def test_unsupported_rule_value_never_becomes_a_rule() -> None:
    # Verification layer: a rule value that the quote does not support
    # must not verify — so it can never reach rule-building as applied.
    from evidence.extract import Clause as ExtractedClause
    from evidence.extract import ClauseStatus, RuleParam, Verification
    from evidence.verify import verify_all

    page = "Room rent is limited to Rs. 3,000 per day of hospitalisation."
    clause = ExtractedClause(
        clause_id="c_bad",
        document_id="doc_test",
        page=1,
        char_start=0,
        char_end=len(page),
        quote=page,
        quote_hash="x",
        rule=RuleParam(type="room_rent_limit", params={"basis": "fixed_per_day", "value": "9999"}),
        verification=Verification(
            schema_valid=True,
            quote_found=True,
            numbers_supported=True,
            interpretation_status=ClauseStatus.VERIFIED,
            reason="",
        ),
    )
    [checked] = verify_all([clause], [page])
    assert checked.verification.numbers_supported is False
    assert checked.verification.interpretation_status != ClauseStatus.VERIFIED


# ---------------------------------------------------------------------------
# Estimate: policy-derived scenario facts
# ---------------------------------------------------------------------------


def test_estimate_uses_selected_policy_facts() -> None:
    suraksha = _session("suraksha-shield-health", "2022")
    aarogya = _session("aarogyakavach-prime", "2022")
    try:
        est = client.get(f"/api/session/{suraksha}/estimate").json()
        # Specified-disease requirement for this condition — NOT the
        # 36-month PED figure from a sibling clause.
        assert est["waiting_months_required"] == 24
        assert est["condition_tag"] == "gallbladder_cholecystectomy"
        assert est["inception_date"] == "2022-07-15"
        assert est["sum_insured"] == "300000"

        est_ak = client.get(f"/api/session/{aarogya}/estimate").json()
        # Sample SI comes from the selected product+version.
        assert est_ak["sum_insured"] == "500000"
        # Gallbladder is not on Aarogya's specified list → no requirement.
        assert est_ak["waiting_months_required"] is None
    finally:
        client.post(f"/api/session/{suraksha}/delete")
        client.post(f"/api/session/{aarogya}/delete")
