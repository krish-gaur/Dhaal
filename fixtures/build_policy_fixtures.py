"""
Build the held-document fixtures for the policy catalogue.

Outputs:
- fixtures/policy_clauses.json            (Suraksha Shield 2022 — EXTENDED
  in place with the initial-waiting, pre-existing-disease and exclusion
  clauses that the existing PDF already contains; original 4 clauses are
  preserved, with `section`/`conditions` params added)
- fixtures/policy_suraksha_shield_2024.pdf + policy_clauses_suraksha_2024.json
  (2024 wording variant: fixed Rs. 4,000/day room limit)
- fixtures/policy_aarogyakavach_prime.pdf + policy_clauses_aarogyakavach.json
  (second fictional policy with materially different rules)
- fixtures/policy_catalogue.json

Every quote is located in the pdfplumber-extracted page text and the
stored offsets slice the RAW extracted text. The script fails loudly if
any quote cannot be found — fixture evidence is never hand-waved.

ALL documents are fictional demonstration policies. No real insurer,
product, UIN, or policy term appears anywhere in these fixtures.

Run (from repo root, with the API venv):  python fixtures/build_policy_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

FIXTURES = Path(__file__).parent
sys.path.insert(0, str(FIXTURES))

from generate_pdf import ALL_PAGES, DISCLAIMER  # noqa: E402  (fixture-local import)

# ---------------------------------------------------------------------------
# Offset handling: search in whitespace-normalised text, map back to raw
# ---------------------------------------------------------------------------


def _normalised_with_map(text: str) -> tuple[str, list[int]]:
    """Whitespace-collapse text, returning (normalised, index_map) where
    index_map[i] is the raw-text index of normalised char i."""
    out: list[str] = []
    idx: list[int] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            out.append(" ")
            idx.append(i)
            i = j
        else:
            out.append(ch)
            idx.append(i)
            i += 1
    return "".join(out), idx


def locate(page_text: str, quote: str) -> tuple[int, int, str]:
    """Find `quote` in page_text (whitespace-insensitive). Returns
    (char_start, char_end, raw_slice) with offsets into the RAW text."""
    want = unicodedata.normalize("NFKC", re.sub(r"\s+", " ", quote)).strip()
    normalised, idx = _normalised_with_map(unicodedata.normalize("NFKC", page_text))
    pos = normalised.find(want)
    if pos == -1:
        raise SystemExit(f"QUOTE NOT FOUND in page text:\n  {quote[:120]}...")
    start = idx[pos]
    end = idx[pos + len(want) - 1] + 1
    return start, end, page_text[start:end]


def quote_hash(quote: str) -> str:
    return "sha256:" + hashlib.sha256(quote.encode("utf-8")).hexdigest()


def extract(pdf_path: Path) -> list[str]:
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def render_pdf(page_texts: list[str], out: Path) -> None:
    """Render page texts like fixtures/generate_pdf.py (Courier, disclaimers)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=7,
        textColor=(0.6, 0.2, 0.1), spaceAfter=6, fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=9, leading=13,
        spaceAfter=4, fontName="Courier",
    )
    story: list[object] = []
    for page_text in page_texts:
        story.append(Paragraph(DISCLAIMER, disclaimer_style))
        story.append(Spacer(1, 0.2 * cm))
        for line in page_text.strip().split("\n"):
            line = line.strip()
            if line:
                line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(line, body_style))
            else:
                story.append(Spacer(1, 0.15 * cm))
        story.append(PageBreak())
    doc.build(story)
    print(f"rendered {out.name}")


def make_clause(
    page_texts: list[str],
    *,
    clause_id: str,
    document_id: str,
    page: int,
    quote: str,
    rule_type: str,
    params: dict[str, str],
    status: str = "verified",
    reason: str = "",
) -> dict[str, object]:
    start, end, raw = locate(page_texts[page - 1], quote)
    return {
        "clause_id": clause_id,
        "document_id": document_id,
        "page": page,
        "char_start": start,
        "char_end": end,
        "quote": raw,
        "quote_hash": quote_hash(raw),
        "rule": {"type": rule_type, "params": params},
        "verification": {
            "schema_valid": True,
            "quote_found": True,
            "numbers_supported": True,
            "interpretation_status": status,
            "reason": reason,
        },
    }


def write_clauses(path: Path, *, document_id: str, document_name: str,
                  page_texts: list[str], clauses: list[dict[str, object]]) -> None:
    payload = {
        "schema_version": 1,
        "document_id": document_id,
        "document_name": document_name,
        "page_count": len(page_texts),
        "clauses": clauses,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.name} ({len(clauses)} clauses)")


# ---------------------------------------------------------------------------
# Suraksha Shield — clause specs shared by the 2022 and 2024 wordings
# ---------------------------------------------------------------------------

SPECIFIED_CONDITIONS = (
    "cataract,hernia,hydrocele,hysterectomy_nonmalignant,"
    "gallbladder_cholecystectomy,kidney_stones_lithotripsy,"
    "benign_prostatic_hypertrophy,varicose_veins,sinusitis"
)
EXCLUSION_CONDITIONS = (
    "cosmetic_treatment,dental_treatment,experimental_treatment,"
    "self_inflicted_injury,substance_dependency_treatment"
)

Q_INITIAL = (
    "A waiting period of 30 days from the policy commencement date applies "
    "to all claims, except those arising from accidents."
)
Q_PED = (
    "Pre-existing diseases are covered after a waiting period of 36 months "
    "from the date of first policy inception"
)
Q_EXCLUSION = (
    "This policy does not cover: (a) Cosmetic or aesthetic treatment "
    "(b) Dental treatment (unless requiring hospitalisation due to accident) "
    "(c) Experimental treatments (d) Self-inflicted injuries "
    "(e) Treatment for alcoholism or drug dependency"
)


def coverage_clauses(
    page_texts: list[str], document_id: str, *, ped_months: str = "36",
    specified_conditions: str = SPECIFIED_CONDITIONS,
    exclusion_conditions: str = EXCLUSION_CONDITIONS,
    exclusion_quote: str = Q_EXCLUSION,
    ped_quote: str = Q_PED,
) -> list[dict[str, object]]:
    """Initial/PED/exclusion clauses present in the Suraksha wording (§4–5)."""
    return [
        make_clause(
            page_texts, clause_id="c_waiting_initial_01", document_id=document_id,
            page=5, quote=Q_INITIAL, rule_type="waiting_period",
            params={
                "scope": "initial", "days_required": "30", "months_required": "0",
                "disease_type": "initial waiting period", "accident_exception": "true",
                "section": "4.1 Initial Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_waiting_ped_01", document_id=document_id,
            page=5, quote=ped_quote, rule_type="waiting_period",
            params={
                "scope": "pre_existing", "months_required": ped_months,
                "disease_type": "pre-existing diseases",
                "section": "4.3 Pre-Existing Disease Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_exclusion_01", document_id=document_id,
            page=6, quote=exclusion_quote, rule_type="exclusion",
            params={
                "conditions": exclusion_conditions,
                "section": "5.2 General Exclusions",
            },
        ),
    ]


def extend_suraksha_2022() -> None:
    """Append coverage clauses to the existing fixture JSON; enrich params.
    Existing clauses keep ids/quotes/offsets/hashes byte-identical."""
    pdf = FIXTURES / "policy_suraksha_shield.pdf"
    page_texts = extract(pdf)
    path = FIXTURES / "policy_clauses.json"
    data = json.loads(path.read_text())
    clauses: list[dict] = data["clauses"]  # type: ignore[type-arg]

    # Verify kept clauses still slice-match the held PDF (normalised).
    for c in clauses:
        raw = page_texts[c["page"] - 1][c["char_start"]:c["char_end"]]
        norm = lambda t: re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip()  # noqa: E731
        assert norm(raw) == norm(c["quote"]), f"offset drift on {c['clause_id']}"

    sections = {
        "c_room_rent_01": "3.1 Room Rent Limit",
        "c_apportionment_01": "3.2 Proportionate Deduction",
        "c_non_payable_01": "5.1 Non-Payable Items",
    }
    for c in clauses:
        if c["clause_id"] in sections:
            c["rule"]["params"]["section"] = sections[c["clause_id"]]
        if c["clause_id"] == "c_waiting_period_01":
            c["rule"]["params"].update({
                "scope": "specified",
                "conditions": SPECIFIED_CONDITIONS,
                "section": "4.2 Specified Disease Waiting Period",
            })

    existing_ids = {c["clause_id"] for c in clauses}
    for extra in coverage_clauses(page_texts, data["document_id"]):
        if extra["clause_id"] not in existing_ids:
            clauses.append(extra)  # type: ignore[arg-type]
    clauses.sort(key=lambda c: (c["page"], c["char_start"]))
    data["clauses"] = clauses
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"extended policy_clauses.json -> {len(clauses)} clauses")


# ---------------------------------------------------------------------------
# Suraksha Shield 2024 — wording variant (fixed room limit)
# ---------------------------------------------------------------------------


def build_suraksha_2024() -> None:
    pages = list(ALL_PAGES)
    p1 = pages[0]
    p1 = p1.replace("Policy Number: SSH/2022/001234 (FICTIONAL)",
                    "Policy Number: SSH/2024/007891 (FICTIONAL)")
    p1 = p1.replace("Policy Period: 01 April 2022 to 31 March 2023",
                    "Policy Period: 01 April 2024 to 31 March 2025")
    p1 = p1.replace("Policy Year: Year 3 (continuous renewal since 2020)",
                    "Policy Year: Year 1\nPolicy Wording Version: 2024 Edition (effective 01 April 2024)")
    pages[0] = p1

    p4 = pages[3]
    p4 = p4.replace(
        "Room rent shall be limited to 1% of Sum Insured per day.",
        "Room rent shall be limited to Rs. 4,000 per day.",
    )
    p4 = p4.replace(
        "For a Sum Insured of Rs. 3,00,000, the eligible room rent is Rs. 3,000 per day.",
        "The eligible room rent under this clause is Rs. 4,000 per day, "
        "irrespective of the Sum Insured.",
    )
    pages[3] = p4

    pdf = FIXTURES / "policy_suraksha_shield_2024.pdf"
    render_pdf(pages, pdf)
    page_texts = extract(pdf)
    doc_id = "doc_suraksha_2024"

    clauses = [
        make_clause(
            page_texts, clause_id="c_room_rent_01", document_id=doc_id, page=4,
            quote=(
                "Room rent shall be limited to Rs. 4,000 per day. In case the "
                "Insured occupies a room with rent exceeding the eligible limit, "
                "all associated medical expenses including surgeon fees, "
                "operation theatre charges, and diagnostic charges shall be "
                "proportionately reduced"
            ),
            rule_type="room_rent_limit",
            params={
                "basis": "fixed_per_day", "value": "4000",
                "section": "3.1 Room Rent Limit",
            },
        ),
        make_clause(
            page_texts, clause_id="c_apportionment_01", document_id=doc_id, page=4,
            quote=(
                'The term "associated medical expenses" includes surgeon fees, '
                "operation theatre charges, anaesthetist fees, and diagnostic "
                "charges. Medicines and consumables are not subject to "
                "proportionate deduction."
            ),
            rule_type="apportionment_base",
            params={
                "scope": "unresolved",
                "candidates": "room_related_only,surgeon_ot_diagnostics",
                "section": "3.2 Proportionate Deduction",
            },
            status="unverified",
            reason=(
                "'associated medical expenses' is partially defined but "
                "excludes medicines — whether diagnostics are included "
                "remains ambiguous."
            ),
        ),
        make_clause(
            page_texts, clause_id="c_waiting_period_01", document_id=doc_id, page=5,
            quote=(
                "A waiting period of 24 months from the date of first policy "
                "inception applies to the following specified diseases and "
                "procedures:"
            ),
            rule_type="waiting_period",
            params={
                "scope": "specified", "months_required": "24",
                "disease_type": "specified_disease",
                "conditions": SPECIFIED_CONDITIONS,
                "section": "4.2 Specified Disease Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_non_payable_01", document_id=doc_id, page=6,
            quote=(
                "The following items are not payable under this policy and "
                "will be deducted from the claim amount:"
            ),
            rule_type="non_payable",
            params={
                "items": "gloves,syringes,admission_kit,attendant_charges,telephone",
                "section": "5.1 Non-Payable Items",
            },
        ),
        *coverage_clauses(page_texts, doc_id),
    ]
    clauses.sort(key=lambda c: (c["page"], c["char_start"]))  # type: ignore[index]
    write_clauses(
        FIXTURES / "policy_clauses_suraksha_2024.json",
        document_id=doc_id,
        document_name="Suraksha Shield Health — Policy Wording (2024)",
        page_texts=page_texts, clauses=clauses,
    )


# ---------------------------------------------------------------------------
# AarogyaKavach Prime — second fictional policy, different rules
# ---------------------------------------------------------------------------

AAK_PAGES = [
    """AAROGYAKAVACH PRIME HEALTH INSURANCE POLICY
Policy Schedule

Policyholder: Sunita Verma (FICTIONAL)
Policy Number: AKP/2022/005432 (FICTIONAL)
Sum Insured: Rs. 5,00,000 (Five Lakh Rupees)
Policy Period: 01 July 2022 to 30 June 2023
Policy Wording Version: 2022 Edition (effective 01 July 2022)
UIN: Not applicable - this is a fictional demonstration product.

Insurer: AarogyaKavach General Insurance Co. Ltd. (FICTIONAL)
This is a fictional policy document created for demonstration purposes only.
It does not represent any real insurance product or insurer.
""",
    """SECTION 1 - LIMITS, CO-PAYMENT AND DEDUCTIBLE

1.1 Room Rent Limit
Room rent shall be limited to Rs. 5,000 per day. If the Insured occupies a
room with rent exceeding Rs. 5,000 per day, the associated medical expenses
shall be proportionately reduced in the ratio of Rs. 5,000 to the actual
room rent charged.

1.2 Associated Medical Expenses - Definition
Associated medical expenses means surgeon fees, operation theatre charges,
anaesthetist fees, and diagnostic charges. Medicines, consumables, and
implants are not associated medical expenses and shall not be
proportionately reduced.

1.3 Co-Payment
The Insured shall bear 10% of the admissible claim amount as co-payment
under this policy.

1.4 Deductible
A deductible of Rs. 5,000 shall apply to each and every claim under this
policy. The Insurer shall not be liable for the first Rs. 5,000 of any
admissible claim.
""",
    """SECTION 2 - WAITING PERIODS

2.1 Initial Waiting Period
A waiting period of 30 days from the policy commencement date applies to
all claims, except those arising from accidents. Claims arising from
accidents are covered from the first day of the policy.

2.2 Specified Disease Waiting Period
A waiting period of 24 months from the date of first policy inception
applies to the following specified diseases and procedures:
(a) Cataract
(b) Hernia (all types)
(c) Joint replacement surgery
(d) Varicose veins
(e) Benign Prostatic Hypertrophy
This waiting period shall not apply if the Insured has had continuous
insurance cover with any Indian non-life insurer for 24 months or more,
subject to proof of continuous cover (portability credit).

2.3 Pre-Existing Disease Waiting Period
Pre-existing diseases are covered after a waiting period of 48 months
from the date of first policy inception, provided the policy has been
continuously renewed without a break.
""",
    """SECTION 3 - EXCLUSIONS AND NON-PAYABLE ITEMS

3.1 General Exclusions
This policy does not cover:
(a) Cosmetic or aesthetic treatment
(b) Bariatric or weight-loss surgery
(c) Dental treatment (unless arising from an accident)
(d) Experimental treatments

3.2 Non-Payable Items
The following items are not payable under this policy and will be deducted
from the claim amount:
(a) Gloves (surgical and examination)
(b) Syringes and needles
(c) Food and beverages for attendants
(d) Telephone charges
(e) Laundry charges
The total deduction for non-payable items shall be as per actual charges
billed by the hospital.
""",
    """SECTION 4 - CLAIMS PROCEDURE

4.1 Pre-Authorisation
For planned hospitalisation, the Insured must obtain pre-authorisation
from the Insurer at least 48 hours before admission.

4.2 Claim Documents
Claims must be supported by the discharge summary, final hospital bill,
investigation reports, and pharmacy bills with prescriptions.

FICTIONAL POLICY ENDS HERE.
This document was created for the DHAAL financial tool demonstration.
It does not represent any actual insurance product.
""",
]


def build_aarogyakavach() -> None:
    pdf = FIXTURES / "policy_aarogyakavach_prime.pdf"
    render_pdf(AAK_PAGES, pdf)
    page_texts = extract(pdf)
    doc_id = "doc_aarogyakavach"

    clauses = [
        make_clause(
            page_texts, clause_id="c_room_rent_01", document_id=doc_id, page=2,
            quote=(
                "Room rent shall be limited to Rs. 5,000 per day. If the "
                "Insured occupies a room with rent exceeding Rs. 5,000 per "
                "day, the associated medical expenses shall be "
                "proportionately reduced"
            ),
            rule_type="room_rent_limit",
            params={"basis": "fixed_per_day", "value": "5000",
                    "section": "1.1 Room Rent Limit"},
        ),
        make_clause(
            page_texts, clause_id="c_apportionment_01", document_id=doc_id, page=2,
            quote=(
                "Associated medical expenses means surgeon fees, operation "
                "theatre charges, anaesthetist fees, and diagnostic charges. "
                "Medicines, consumables, and implants are not associated "
                "medical expenses"
            ),
            rule_type="apportionment_base",
            params={
                "scope": "surgeon_ot_diagnostics",
                "candidates": "surgeon_ot_diagnostics",
                "section": "1.2 Associated Medical Expenses - Definition",
            },
        ),
        make_clause(
            page_texts, clause_id="c_copayment_01", document_id=doc_id, page=2,
            quote="The Insured shall bear 10% of the admissible claim amount as co-payment",
            rule_type="co_payment",
            params={"pct": "0.10", "section": "1.3 Co-Payment"},
        ),
        make_clause(
            page_texts, clause_id="c_deductible_01", document_id=doc_id, page=2,
            quote="A deductible of Rs. 5,000 shall apply to each and every claim under this policy.",
            rule_type="deductible",
            params={"amount": "5000", "section": "1.4 Deductible"},
        ),
        make_clause(
            page_texts, clause_id="c_waiting_initial_01", document_id=doc_id, page=3,
            quote=Q_INITIAL, rule_type="waiting_period",
            params={
                "scope": "initial", "days_required": "30", "months_required": "0",
                "disease_type": "initial waiting period", "accident_exception": "true",
                "section": "2.1 Initial Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_waiting_period_01", document_id=doc_id, page=3,
            quote=(
                "A waiting period of 24 months from the date of first policy "
                "inception applies to the following specified diseases and "
                "procedures:"
            ),
            rule_type="waiting_period",
            params={
                "scope": "specified", "months_required": "24",
                "disease_type": "specified_disease",
                "conditions": (
                    "cataract,hernia,joint_replacement,varicose_veins,"
                    "benign_prostatic_hypertrophy"
                ),
                "section": "2.2 Specified Disease Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_waiting_ped_01", document_id=doc_id, page=3,
            quote=(
                "Pre-existing diseases are covered after a waiting period of "
                "48 months from the date of first policy inception"
            ),
            rule_type="waiting_period",
            params={
                "scope": "pre_existing", "months_required": "48",
                "disease_type": "pre-existing diseases",
                "section": "2.3 Pre-Existing Disease Waiting Period",
            },
        ),
        make_clause(
            page_texts, clause_id="c_exclusion_01", document_id=doc_id, page=4,
            quote=(
                "This policy does not cover: (a) Cosmetic or aesthetic "
                "treatment (b) Bariatric or weight-loss surgery (c) Dental "
                "treatment (unless arising from an accident) (d) Experimental "
                "treatments"
            ),
            rule_type="exclusion",
            params={
                "conditions": (
                    "cosmetic_treatment,bariatric_surgery,dental_treatment,"
                    "experimental_treatment"
                ),
                "section": "3.1 General Exclusions",
            },
        ),
        make_clause(
            page_texts, clause_id="c_non_payable_01", document_id=doc_id, page=4,
            quote=(
                "The following items are not payable under this policy and "
                "will be deducted from the claim amount:"
            ),
            rule_type="non_payable",
            params={
                "items": "gloves,syringes,attendant_food,telephone,laundry",
                "section": "3.2 Non-Payable Items",
            },
        ),
    ]
    clauses.sort(key=lambda c: (c["page"], c["char_start"]))  # type: ignore[index]
    write_clauses(
        FIXTURES / "policy_clauses_aarogyakavach.json",
        document_id=doc_id,
        document_name="AarogyaKavach Prime — Policy Wording (2022)",
        page_texts=page_texts, clauses=clauses,
    )


# ---------------------------------------------------------------------------
# Catalogue — ONLY documents actually held in this repo, hash-verifiable.
# ---------------------------------------------------------------------------


def write_catalogue() -> None:
    catalogue = {
        "schema_version": 1,
        "note": (
            "This catalogue lists only policy documents Dhaal actually holds "
            "and can hash-verify. All entries are FICTIONAL sample policies "
            "created for demonstration; they are not real insurance products "
            "and carry no UIN. If your policy is not listed, upload your "
            "policy PDF — Dhaal will not guess your wording."
        ),
        "products": [
            {
                "product_id": "suraksha-shield-health",
                "insurer": "Suraksha General Insurance Co. Ltd.",
                "product_name": "Suraksha Shield Health",
                "uin": None,
                "fictional": True,
                "versions": [
                    {
                        "version": "2022",
                        "effective_date": "2022-04-01",
                        "sample_sum_insured": "300000",
                        "document": {
                            "pdf_file": "policy_suraksha_shield.pdf",
                            "clauses_file": "policy_clauses.json",
                            "document_name": "Suraksha Shield Health — Policy Wording (2022)",
                        },
                    },
                    {
                        "version": "2024",
                        "effective_date": "2024-04-01",
                        "sample_sum_insured": "300000",
                        "document": {
                            "pdf_file": "policy_suraksha_shield_2024.pdf",
                            "clauses_file": "policy_clauses_suraksha_2024.json",
                            "document_name": "Suraksha Shield Health — Policy Wording (2024)",
                        },
                    },
                ],
            },
            {
                "product_id": "aarogyakavach-prime",
                "insurer": "AarogyaKavach General Insurance Co. Ltd.",
                "product_name": "AarogyaKavach Prime",
                "uin": None,
                "fictional": True,
                "versions": [
                    {
                        "version": "2022",
                        "effective_date": "2022-07-01",
                        "sample_sum_insured": "500000",
                        "document": {
                            "pdf_file": "policy_aarogyakavach_prime.pdf",
                            "clauses_file": "policy_clauses_aarogyakavach.json",
                            "document_name": "AarogyaKavach Prime — Policy Wording (2022)",
                        },
                    },
                ],
            },
        ],
    }
    (FIXTURES / "policy_catalogue.json").write_text(
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n"
    )
    print("wrote policy_catalogue.json")


def main() -> None:
    extend_suraksha_2022()
    build_suraksha_2024()
    build_aarogyakavach()
    write_catalogue()
    print("done")


if __name__ == "__main__":
    main()
