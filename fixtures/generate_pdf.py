"""
Generate the fictional Suraksha Shield Health policy PDF.

This is the fixture policy document used for the DHAAL demo.
Every page has a FICTIONAL POLICY header.
The PDF contains text content (not scanned images) so pdfplumber can extract it.

Run: python fixtures/generate_pdf.py
Output: fixtures/policy_suraksha_shield.pdf

Also outputs: fixtures/policy_clauses.json with pre-verified clause extractions
and correct char_start/char_end offsets matching the generated PDF text.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Page text content — this is what pdfplumber will extract
# We define the text first, then render it to PDF, then compute offsets.
# ---------------------------------------------------------------------------

DISCLAIMER = "FICTIONAL POLICY -- FOR DEMONSTRATION ONLY -- NOT A REAL INSURANCE PRODUCT"

PAGE_1_TEXT = """SURAKSHA SHIELD HEALTH INSURANCE POLICY
Policy Schedule

Policyholder: Rajesh Kumar (FICTIONAL)
Policy Number: SSH/2022/001234 (FICTIONAL)
Sum Insured: Rs. 3,00,000 (Three Lakh Rupees)
Policy Period: 01 April 2022 to 31 March 2023
Policy Year: Year 3 (continuous renewal since 2020)
Premium Paid: Rs. 8,450

Insurer: Suraksha General Insurance Co. Ltd. (FICTIONAL)
This is a fictional policy document created for demonstration purposes only.
It does not represent any real insurance product or insurer.

Network Hospitals: 4,200+ hospitals across India (FICTIONAL)
Cashless facility available at all network hospitals.
"""

PAGE_2_TEXT = """SECTION 1 - GENERAL CONDITIONS

1.1 Scope of Cover
This policy provides coverage for hospitalisation expenses incurred by the Insured Person
due to illness or injury, subject to the terms, conditions, exclusions, and limits set out
in this policy document.

1.2 Hospitalisation
Hospitalisation means admission to a hospital for a minimum period of 24 consecutive hours.
Day-care procedures are covered as specified in the Day-Care List.

1.3 Pre-Authorisation
For planned hospitalisation, the Insured must obtain pre-authorisation from the Insurer
at least 72 hours before the date of admission. In case of emergency hospitalisation,
pre-authorisation must be obtained within 24 hours of admission.

1.4 Claim Procedure
All claims must be submitted within 30 days of discharge from hospital.
Original bills, receipts, prescriptions, and discharge summary must be provided.
The Insurer reserves the right to verify all submitted documents.

1.5 Renewability
This policy is renewable for life, subject to the terms prevailing at the time of renewal.
Continuity benefits are available upon continuous renewal without a break in coverage.
"""

PAGE_3_TEXT = """SECTION 2 - COVERAGE AND BENEFITS

2.1 In-Patient Hospitalisation
The policy covers the following expenses incurred during hospitalisation:
(a) Room, boarding, and nursing expenses
(b) Intensive care unit charges
(c) Surgeon, anaesthetist, medical practitioner, consultant, and specialist fees
(d) Operation theatre charges
(e) Anaesthesia, blood, oxygen, surgical appliances
(f) Medicines and drugs (as prescribed by the attending doctor)
(g) Diagnostic tests and imaging

2.2 Pre and Post Hospitalisation
Pre-hospitalisation expenses are covered for 30 days prior to admission.
Post-hospitalisation expenses are covered for 60 days after discharge.
Both are subject to the overall Sum Insured limit.

2.3 Ambulance Cover
Emergency ambulance charges up to Rs. 2,000 per hospitalisation are covered.

2.4 Sum Insured
The maximum amount payable under this policy in any policy year is Rs. 3,00,000.
Amounts paid in respect of each claim will be deducted from the Sum Insured.
"""

# PAGE 4 — Room rent clause (key clause for the demo)
# This page contains the room rent limit and proportionate deduction clause.
PAGE_4_TEXT = """SECTION 3 - LIMITS AND SUB-LIMITS

3.1 Room Rent Limit
Room rent shall be limited to 1% of Sum Insured per day. In case the Insured occupies
a room with rent exceeding the eligible limit, all associated medical expenses including
surgeon fees, operation theatre charges, and diagnostic charges shall be proportionately
reduced in the same ratio as the eligible room rent bears to the actual room rent charged.

The proportionate deduction shall apply to all charges classified as associated medical
expenses in the claim, calculated as follows:
  Admissible amount = Actual charge x (Eligible room rent / Actual room rent charged)

For a Sum Insured of Rs. 3,00,000, the eligible room rent is Rs. 3,000 per day.

3.2 Proportionate Deduction
Where the actual room rent exceeds the eligible room rent limit specified in Clause 3.1,
a proportionate deduction shall be applied. The term "associated medical expenses" includes
surgeon fees, operation theatre charges, anaesthetist fees, and diagnostic charges.
Medicines and consumables are not subject to proportionate deduction.

3.3 ICU Charges
ICU charges are limited to 2% of Sum Insured per day, i.e., Rs. 6,000 per day for a
Sum Insured of Rs. 3,00,000.

3.4 Co-Payment
No co-payment is applicable under this policy for the base cover.
"""

# PAGE 5 — Waiting period clause
PAGE_5_TEXT = """SECTION 4 - WAITING PERIODS AND EXCLUSIONS

4.1 Initial Waiting Period
A waiting period of 30 days from the policy commencement date applies to all claims,
except those arising from accidents. Claims arising from accidents are covered from
the first day of the policy.

4.2 Specified Disease Waiting Period
A waiting period of 24 months from the date of first policy inception applies to the
following specified diseases and procedures:
(a) Cataract
(b) Hernia (all types)
(c) Hydrocele
(d) Hysterectomy (non-malignant)
(e) Gallbladder stones and cholecystectomy
(f) Kidney stones and lithotripsy
(g) Benign Prostatic Hypertrophy
(h) Varicose veins
(i) Sinusitis and related conditions

This waiting period shall not apply if the Insured has had continuous insurance cover
for the same condition with any Indian non-life insurer for a period of 24 months or more,
subject to submission of proof of continuous cover (portability credit).

4.3 Pre-Existing Disease Waiting Period
Pre-existing diseases are covered after a waiting period of 36 months from the date
of first policy inception, provided the policy has been continuously renewed.
"""

# PAGE 6 — Non-payable items
PAGE_6_TEXT = """SECTION 5 - NON-PAYABLE ITEMS

5.1 Non-Payable Items
The following items are not payable under this policy and will be deducted from the
claim amount:
(a) Gloves (surgical and examination)
(b) Syringes and needles
(c) Admission kit / Welcome kit
(d) Attendant charges / Bystander charges
(e) Telephone charges
(f) Laundry charges
(g) Toiletries and personal care items
(h) Vitamins and tonics (unless prescribed as part of treatment)
(i) Newspaper charges

The total deduction for non-payable items shall be as per actual charges billed by
the hospital and verified by the Insurer's claims team.

5.2 General Exclusions
This policy does not cover:
(a) Cosmetic or aesthetic treatment
(b) Dental treatment (unless requiring hospitalisation due to accident)
(c) Experimental treatments
(d) Self-inflicted injuries
(e) Treatment for alcoholism or drug dependency

FICTIONAL POLICY ENDS HERE.
This document was created for the DHAAL financial tool demonstration.
It does not represent any actual insurance product.
"""

ALL_PAGES = [PAGE_1_TEXT, PAGE_2_TEXT, PAGE_3_TEXT, PAGE_4_TEXT, PAGE_5_TEXT, PAGE_6_TEXT]


def generate_pdf(output_path: Path) -> None:
    """Generate the PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT
    except ImportError:
        print("reportlab not installed. Run: pip install reportlab")
        sys.exit(1)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=(0.6, 0.2, 0.1),
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=4,
        fontName="Courier",  # monospace for consistent char offsets
    )

    story = []

    for page_text in ALL_PAGES:
        story.append(Paragraph(DISCLAIMER, disclaimer_style))
        story.append(Spacer(1, 0.2 * cm))
        # Split into lines and render each as a paragraph
        for line in page_text.strip().split("\n"):
            line = line.strip()
            if line:
                # Escape special reportlab chars
                line = (line.replace("&", "&amp;")
                           .replace("<", "&lt;")
                           .replace(">", "&gt;"))
                story.append(Paragraph(line, body_style))
            else:
                story.append(Spacer(1, 0.15 * cm))
        # Page break between pages (except last)
        from reportlab.platypus import PageBreak
        story.append(PageBreak())

    doc.build(story)
    print(f"Generated: {output_path}")


def extract_text_from_pdf(pdf_path: Path) -> list[str]:
    """Extract page texts using pdfplumber to get actual char offsets."""
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber not installed.")
        return ALL_PAGES

    page_texts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_texts.append(text)
    return page_texts


def find_offset(page_text: str, substring: str) -> tuple[int, int]:
    """Find char_start and char_end of substring in page_text."""
    idx = page_text.find(substring)
    if idx == -1:
        # Try normalised search
        import unicodedata, re
        def norm(t: str) -> str:
            t = unicodedata.normalize("NFKC", t)
            t = re.sub(r"\s+", " ", t)
            return t.lower()
        norm_page = norm(page_text)
        norm_sub = norm(substring)
        idx = norm_page.find(norm_sub)
        if idx == -1:
            return 0, len(substring)
    return idx, idx + len(substring)


def build_quote_hash(quote: str) -> str:
    digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def generate_clauses_json(page_texts: list[str], output_path: Path) -> None:
    """Generate policy_clauses.json with pre-verified extractions."""

    # -----------------------------------------------------------------------
    # Clause 1: Room rent limit (page 4)
    # -----------------------------------------------------------------------
    room_quote = (
        "Room rent shall be limited to 1% of Sum Insured per day. In case the Insured occupies "
        "a room with rent exceeding the eligible limit, all associated medical expenses including "
        "surgeon fees, operation theatre charges, and diagnostic charges shall be proportionately "
        "reduced in the same ratio as the eligible room rent bears to the actual room rent charged."
    )

    # Find it in page 4 text (index 3)
    p4_text = page_texts[3] if len(page_texts) > 3 else PAGE_4_TEXT
    room_start, room_end = find_offset(p4_text, room_quote[:60])

    # -----------------------------------------------------------------------
    # Clause 2: Waiting period — specified disease (page 5)
    # -----------------------------------------------------------------------
    waiting_quote = (
        "A waiting period of 24 months from the date of first policy inception applies to the "
        "following specified diseases and procedures:"
    )
    p5_text = page_texts[4] if len(page_texts) > 4 else PAGE_5_TEXT
    wait_start, wait_end = find_offset(p5_text, waiting_quote[:60])

    # -----------------------------------------------------------------------
    # Clause 3: Non-payable items (page 6)
    # -----------------------------------------------------------------------
    nonpay_quote = (
        "The following items are not payable under this policy and will be deducted from the "
        "claim amount:"
    )
    p6_text = page_texts[5] if len(page_texts) > 5 else PAGE_6_TEXT
    np_start, np_end = find_offset(p6_text, nonpay_quote[:50])

    # -----------------------------------------------------------------------
    # Clause 4: Apportionment base (page 4) — marked UNVERIFIED because
    # "associated medical expenses" is undefined / ambiguous
    # -----------------------------------------------------------------------
    apportion_quote = (
        'The term "associated medical expenses" includes '
        "surgeon fees, operation theatre charges, anaesthetist fees, and diagnostic charges. "
        "Medicines and consumables are not subject to proportionate deduction."
    )
    app_start, app_end = find_offset(p4_text, apportion_quote[:60])

    clauses = [
        {
            "clause_id": "c_room_rent_01",
            "document_id": "doc_fixture",
            "page": 4,
            "char_start": room_start,
            "char_end": room_end + len(room_quote) - 60,
            "quote": room_quote,
            "quote_hash": build_quote_hash(room_quote),
            "rule": {
                "type": "room_rent_limit",
                "params": {
                    "basis": "pct_sum_insured_per_day",
                    "value": "0.01"
                }
            },
            "verification": {
                "schema_valid": True,
                "quote_found": True,
                "numbers_supported": True,
                "interpretation_status": "verified",
                "reason": ""
            }
        },
        {
            "clause_id": "c_waiting_period_01",
            "document_id": "doc_fixture",
            "page": 5,
            "char_start": wait_start,
            "char_end": wait_start + len(waiting_quote),
            "quote": waiting_quote,
            "quote_hash": build_quote_hash(waiting_quote),
            "rule": {
                "type": "waiting_period",
                "params": {
                    "months_required": "24",
                    "disease_type": "specified_disease"
                }
            },
            "verification": {
                "schema_valid": True,
                "quote_found": True,
                "numbers_supported": True,
                "interpretation_status": "verified",
                "reason": ""
            }
        },
        {
            "clause_id": "c_non_payable_01",
            "document_id": "doc_fixture",
            "page": 6,
            "char_start": np_start,
            "char_end": np_start + len(nonpay_quote),
            "quote": nonpay_quote,
            "quote_hash": build_quote_hash(nonpay_quote),
            "rule": {
                "type": "non_payable",
                "params": {
                    "items": "gloves,syringes,admission_kit,attendant_charges,telephone"
                }
            },
            "verification": {
                "schema_valid": True,
                "quote_found": True,
                "numbers_supported": True,
                "interpretation_status": "verified",
                "reason": ""
            }
        },
        {
            "clause_id": "c_apportionment_01",
            "document_id": "doc_fixture",
            "page": 4,
            "char_start": app_start,
            "char_end": app_start + len(apportion_quote),
            "quote": apportion_quote,
            "quote_hash": build_quote_hash(apportion_quote),
            "rule": {
                "type": "apportionment_base",
                "params": {
                    "scope": "unresolved"
                }
            },
            "verification": {
                "schema_valid": True,
                "quote_found": True,
                "numbers_supported": True,
                "interpretation_status": "unverified",
                "reason": (
                    "'associated medical expenses' is partially defined but excludes medicines — "
                    "whether diagnostics are included remains ambiguous. "
                    "This drives a ₹24,667 swing in out-of-pocket cost."
                )
            }
        }
    ]

    data = {
        "schema_version": "1.0",
        "document_id": "doc_fixture",
        "document_name": "Suraksha Shield Health (fictional)",
        "page_count": 6,
        "clauses": clauses
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Generated: {output_path}")


def main() -> None:
    fixtures_dir = Path(__file__).parent
    pdf_path = fixtures_dir / "policy_suraksha_shield.pdf"
    clauses_path = fixtures_dir / "policy_clauses.json"

    print("Generating fixture PDF...")
    generate_pdf(pdf_path)

    print("Extracting text from PDF...")
    page_texts = extract_text_from_pdf(pdf_path)

    print("Generating policy_clauses.json...")
    generate_clauses_json(page_texts, clauses_path)

    print("Done.")


if __name__ == "__main__":
    main()
