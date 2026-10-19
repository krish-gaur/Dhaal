# DHAAL (ढाल) — Implementation Task List

> Spec-mode document. Review and approve before implementation begins.
> Tasks are ordered by gate. Do not begin a gate until the previous gate's exit condition is met and verified by running the listed commands.
> Version 0.1 — initial draft

---

## Gate G1 — Financial Engine + Tests

**Exit condition:** `pnpm test:api` passes every golden value in §6.4 and §6.5 of the product spec. Zero failures. No UI work begins until this gate is green.

---

### T1.1 — Project scaffolding

Set up the monorepo skeleton. No application code yet.

- [ ] Create `dhaal/` root with `pnpm-workspace.yaml` listing `apps/*`
- [ ] Create `apps/api/` with `pyproject.toml` declaring: `fastapi`, `uvicorn`, `pdfplumber`, `pydantic[v2]`, `sqlalchemy`, `python-multipart`, `python-magic`, `anthropic`, `openai`, `hypothesis`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- [ ] Create `apps/web/` with `package.json` for Next.js 15, TypeScript strict, Tailwind CSS, `@playwright/test`
- [ ] Create root `package.json` with scripts: `dev`, `build`, `test:api`, `test:e2e`, `lint`
- [ ] Create `.env.example` with placeholders: `ANTHROPIC_API_KEY=`, `OPENAI_API_KEY=`, `DATABASE_URL=sqlite:///./dhaal.db`
- [ ] Create `.gitignore` covering: `.env`, `__pycache__`, `*.pyc`, `.next`, `node_modules`, `*.db`
- [ ] Verify: `pnpm install` exits 0

---

### T1.2 — Engine type definitions

Create all Python types. No logic yet.

- [ ] Create `apps/api/engine/rules.py`
  - `RuleType` enum (6 values)
  - `ApportionmentBase` enum (4 values including `UNRESOLVED`)
  - `RoomLimit` frozen dataclass: `basis: Literal[...]`, `value: Decimal`
  - `WaitingPeriod` frozen dataclass: `disease_type`, `months_required`, `months_elapsed`
  - `NonPayableList` frozen dataclass: `items: list[str]`, `total: Decimal`
  - `CoPayment` frozen dataclass: `pct: Decimal`
  - `ProportionateRule` frozen dataclass: `trigger: Literal["room_above_cap"]`
  - `PolicyRules` frozen dataclass — all fields as per design.md §3.1, `room_limit: RoomLimit | None` (never a default)
  - `ChargeItem` frozen dataclass: `name`, `amount`, `nights | None`
  - `ClaimInputs` frozen dataclass: all fields
  - `Deduction` frozen dataclass: `name`, `amount`, `basis`, `rule_id`, `citation`
  - `UnresolvedRule` frozen dataclass: `rule_type`, `reason`, `low_impact`, `high_impact`
  - `ClaimResult` frozen dataclass: all fields, `invariants_ok: bool`
  - `InvariantError(Exception)` — raised on conservation failure, never swallowed
- [ ] `mypy --strict apps/api/engine/rules.py` exits 0

---

### T1.3 — Claim engine implementation

- [ ] Create `apps/api/engine/claim.py`
  - `simulate_claim(rules: PolicyRules, inputs: ClaimInputs) -> ClaimResult`
  - Waterfall iterates `rules.waterfall` in order
  - Step 1: waiting period check → if any period unsatisfied, return zero insurer payment immediately
  - Step 2: non-payable deduction (`admissible_0 = gross - non_payable_total`)
  - Step 3: room cap (`room_eligible = cap_per_day * nights`, `room_deduction = max(0, billed - eligible)`)
  - Step 4: proportionate deduction — ratio from `Decimal` division (full precision), `base` from `apportionment_base` enum, `deduction = base * (1 - ratio)`; if `apportionment_base == UNRESOLVED` add to `unresolved` list
  - Step 5: co-payment (pct of net admissible at that point); if `co_payment is None` skip
  - Step 6: deductible; if `deductible is None` skip
  - Step 7: `net_admissible = gross - Σ(all deductions)`
  - Step 8: `insurer_payment = floor(clamp(net_admissible, 0, remaining_si))` — `ROUND_FLOOR`, applied exactly once, documented in a comment
  - Step 9: `out_of_pocket = gross - insurer_payment`
  - Step 10: call `assert_conservation`; on failure raise `InvariantError`
  - `range_low`/`range_high` populated when `unresolved` is non-empty
  - Every `Deduction` object carries human-readable `basis` string (e.g. `"₹74,000 × (1 − 0.6667)"`)

- [ ] Create `apps/api/engine/invariants.py`
  - `assert_conservation(gross, insurer, oop)` — raises `InvariantError` with message if `insurer + oop != gross`
  - `assert_monotonicity_charge(result_a, result_b)` — asserts that raising an admissible charge does not reduce insurer payment
  - `assert_monotonicity_cap(result_low_cap, result_high_cap)` — asserts higher room cap does not increase OOP

---

### T1.4 — Loan engine implementation

- [ ] Create `apps/api/engine/loans.py`
  - `LoanOffer` and `LoanMetrics` dataclasses (as per design.md §3.3)
  - `emi(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal`
    - Standard formula: `P * r * (1+r)^n / ((1+r)^n - 1)` where `r = annual_rate/12`
    - Edge: `months <= 0` → `ValueError`; `annual_rate < 0` → `ValueError`; `rate == 0` → `principal / months`
  - `apr_from_cashflows(net_received: Decimal, payment: Decimal, months: int) -> tuple[Decimal, Decimal]`
    - Bisection on `r ∈ [0.000001, 10.0]`, convergence `|f(r)| < 1e-9`, max 200 iterations
    - Returns `(nominal = r*12, effective = (1+r)^12 - 1)`
    - Edge: `months <= 0` → `ValueError`; `net_received <= 0` → `ValueError`
  - `compute_loan_metrics(offer: LoanOffer, affordability: AffordabilityContext) -> LoanMetrics`
    - `net_disbursed = principal - processing_fee - gst_on_fee - credit_life_premium`
    - `total_repayment = emi * months`
    - `total_interest = total_repayment - principal`
    - `total_cash_out = total_repayment + processing_fee + gst_on_fee + credit_life_premium`
    - `emi_pct_of_mean = emi / mean_income`
    - `emi_pct_of_lean = emi / lean_income`
    - `free_cash_avg_month = avg_free_cash - emi`
    - `free_cash_lean_month = lean_free_cash - emi`

- [ ] Create `apps/api/engine/affordability.py`
  - `AffordabilityContext` dataclass: `income_months`, `essentials`, `existing_emi`, `savings`
  - `compute_affordability(ctx: AffordabilityContext) -> AffordabilitySummary`
    - `mean` (to paisa precision), `median`, `lowest_observed`
    - `avg_free_cash = mean - essentials - existing_emi`
    - `lean_free_cash = lowest_observed - essentials - existing_emi`
    - `emergency_runway = savings / mean` (months, 2dp)
    - `obligations_at_lean_pct = (essentials + existing_emi) / lowest_observed`

---

### T1.5 — Attribution engine implementation

- [ ] Create `apps/api/engine/attribution.py`
  - `FieldChange` dataclass: `field: str`, `from_val: Any`, `to_val: Any`
  - `apply_change(inputs: ClaimInputs, change: FieldChange) -> ClaimInputs`
    - Supports fields: `room_rate_per_night`, `policy_month_at_admit`, `gross_bill`
    - Unknown field → `ValueError`
  - `counterfactual(rules, inputs, change) -> CounterfactualResult`
  - `interaction_check(rules, inputs, change_a, change_b) -> Decimal`
    - Returns `(r_ab - r_base) - (r_a - r_base) - (r_b - r_base)`
    - Zero means additive; non-zero means the changes interact

---

### T1.6 — Engine tests (must all pass before G1 is done)

- [ ] Create `apps/api/tests/test_claim.py`
  - Scenario A: waiting period applies → `insurer = 0`, `oop = 120000`
  - Scenario B: continuity confirmed, room above cap → `insurer = 81333`, `oop = 38667`
  - Scenario B intermediate values: `non_payable = 9500`, `admissible_0 = 110500`, `room_eligible = 9000`, `room_deduction = 4500`, `ratio ≈ 0.6667`, `apportionment_base = 74000`, `proportionate_deduction ≈ 24667`, `net_admissible ≈ 81333.33`
  - Scenario C1: room at cap, bill ₹1,20,000 → `insurer = 110500`, `oop = 9500`
  - Scenario C2: room at cap, bill ₹1,15,500 → `insurer = 106000`, `oop = 9500`
  - Conservation invariant: `insurer + oop == gross` for A, B, C1, C2
  - Edge: `gross = 0` → `insurer = 0`, `oop = 0`
  - Edge: `gross = 50000000` (₹5Cr) → no exception, conservation holds
  - Edge: `room_limit = None` → result contains `unresolved` entry, no numeric deduction applied
  - Co-pay test: 10% co-pay on scenario B → `insurer` and `oop` correct, conservation holds
  - Deductible test: ₹10,000 deductible on scenario B → correct, conservation holds

- [ ] Create `apps/api/tests/test_loans.py`
  - EMI formula: offer A → `4001.25` (assert to 2dp)
  - EMI formula: offer B → `2762.71`
  - EMI formula: offer C → `5262.79`
  - `net_disbursed`: A → `82994.00`, B → `81489.50`, C → `82497.00`
  - `total_repayment`: A → `96029.88` (allow rounding to 2dp via `ROUND_HALF_UP` on per-period accumulation; document rule)
  - `total_cash_out`: A → `98035.88`, B → `102967.98`, C → `97233.22`
  - APR nominal: A → `14.42%`, B → `13.43%`, C → `17.97%` (assert to 2dp)
  - APR effective: A → `15.41%`, B → `14.29%`, C → `19.53%`
  - Zero-fee loan: `apr_from_cashflows` returns nominal ≈ stated rate within 1bp
  - `months <= 0` → `ValueError`
  - `net_received <= 0` → `ValueError`
  - Rate = 0%, fee = 0 → APR = 0
  - Affordability: lean month free cash A → `−4201.25`, B → `−2962.71`, C → `−5462.79`

- [ ] Create `apps/api/tests/test_attribution.py`
  - A→B delta: `+81333` (continuity change)
  - B→C1 delta: `+29167` (room at cap change)
  - A→C1: `+110500` (both) — computed via full simulation, not addition
  - Additivity check: `(A→B delta) + (B→C1 delta) == (A→C1 delta)` for fixture rule set
  - Interaction residual test: construct a co-pay + room-cap case where `interaction_residual != 0` — assert non-zero

- [ ] Create `apps/api/tests/test_invariants.py` (property-based)
  - Hypothesis strategy: `gross ∈ [1000, 1_000_000]`, random non-payable fraction, random room rate, random cap
  - Conservation: `insurer + oop == gross` over 10,000 examples
  - Monotonicity charge: raising an admissible charge by ₹1 does not reduce `insurer_payment`
  - Monotonicity cap: raising room cap by ₹100 does not increase `out_of_pocket`
  - Missing room limit (None): result has `unresolved`, `insurer_payment` is not set to a value assuming zero deduction

- [ ] Run `pnpm test:api` — all tests green before proceeding

**G1 exit command:** `pnpm test:api` → 0 failures, all golden values to 2dp

---

## Gate G2 — Evidence Schema, Verifier, Fixture Provider, Fixtures

**Exit condition:** `pnpm test:api` still green; `test_verify.py` all passing; fixture provider runs all five screen flows without network; golden JSON extracts correctly from the fixture PDF.

---

### T2.1 — Evidence type definitions

- [ ] Create `apps/api/evidence/extract.py`
  - `ClauseStatus` enum (6 values, exactly)
  - `Verification` frozen dataclass
  - `RuleParam` dataclass
  - `Clause` frozen dataclass — all fields as per design.md §3.2
  - `ExtractionProvider` Protocol with `extract_clauses` signature

---

### T2.2 — Deterministic verification pipeline

- [ ] Create `apps/api/evidence/verify.py`
  - `normalise(text: str) -> str` — NFKC, whitespace collapse, quote/dash unification, soft-hyphen strip, lowercase
  - `check_injection(text: str) -> bool` — checks markers and codepoints from design.md §5.3
  - `verify_quote(clause: Clause, page_texts: list[str]) -> Clause` — steps 1–5 of verification pipeline
  - `detect_conflicts(clauses: list[Clause]) -> list[Clause]` — marks both sides of any conflict
  - Each step returns a new `Clause` instance (immutable); status fields updated
  - `quote_found` and `interpretation_status` are always separate fields; never collapsed

---

### T2.3 — Provider implementations

- [ ] Create `apps/api/evidence/providers/base.py` — `ExtractionProvider` Protocol
- [ ] Create `apps/api/evidence/providers/fixture.py` — `FixtureProvider`
  - Reads `fixtures/policy_clauses.json`
  - Returns `list[Clause]` without any network call
  - Works when called with network disabled
- [ ] Create `apps/api/evidence/providers/anthropic.py` — `AnthropicProvider`
  - Wraps document in `<document>…</document>`
  - System prompt: injection-containment instructions (design.md §9.1)
  - `tools=[]` on the API call
  - On failure: falls back to `FixtureProvider`, sets `mode = "fixture"` on session
- [ ] Create `apps/api/evidence/providers/openai.py` — `OpenAIProvider`
  - Same containment setup as Anthropic
  - On failure: same fallback
- [ ] `get_provider()` function in `extract.py` — reads env vars, returns correct provider

---

### T2.4 — Fixture files

- [ ] Create `fixtures/generate_pdf.py` — Python script using `reportlab`
  - 6 pages, FICTIONAL header on every page
  - Page 4: room rent clause with exact wording ("1% of Sum Insured per day"), proportionate deduction paragraph
  - Page 5: waiting period clause ("24 months for specified diseases")
  - Page 6: non-payable items list (total ₹9,500)
  - Run script: `python fixtures/generate_pdf.py` → produces `fixtures/policy_suraksha_shield.pdf`
- [ ] Create `fixtures/policy_clauses.json` — pre-verified extraction
  - Room rent: `status: "verified"`, correct `char_start`/`char_end`, correct `quote_hash`
  - Waiting period: `status: "verified"`
  - Non-payables: `status: "verified"`
  - Apportionment base: `status: "unverified"`, `reason: "'associated medical expenses' undefined"`
- [ ] Create `fixtures/hospital_estimate.json` — exact values from design.md §8.3
- [ ] Create `fixtures/income_history.json` — exact values from design.md §8.4
- [ ] Create `fixtures/loan_offers.json` — exact values from design.md §8.5, `"synthetic": true`

---

### T2.5 — Evidence tests

- [ ] Create `apps/api/tests/test_verify.py`
  - Quote found: clause quote is substring of page text after normalisation → `quote_found = True`
  - Quote not found: altered quote → `quote_found = False`, `status = UNVERIFIED`
  - Normalisation: curly quotes, soft hyphens, extra whitespace all handled correctly
  - Number support: rule says "1%", quote says "2%" → `numbers_supported = False`
  - Rule-type validation: unknown rule type → `status = UNKNOWN`
  - Conflict detection: two room-rent clauses with different values → both `status = CONFLICTING`
  - Injection quarantine: document containing "ignore previous" → `check_injection` returns `True`
  - Injection quarantine: U+200B in document → `check_injection` returns `True`
  - Fixture provider: returns exactly the clauses from `policy_clauses.json`, no network required

**G2 exit command:** `pnpm test:api` → all tests green (including `test_verify.py`)

---

## Gate G3 — API Routes

**Exit condition:** All API endpoints return correct shapes; the e2e test can drive all routes; engine and evidence layers are wired up.

---

### T3.1 — Database layer

- [ ] Create `apps/api/db/models.py` — SQLAlchemy models matching the schema in design.md §3.4
- [ ] Create `apps/api/db/session_store.py`
  - `get_session(session_id) -> Session | None`
  - `create_session(mode, goal) -> Session`
  - `delete_session(session_id) -> dict[str, int]` — returns counts of deleted rows
  - `get_session_db()` — FastAPI dependency
- [ ] Create `apps/api/db/migrations/001_initial.sql` — exact SQL from design.md §3.4
- [ ] DB is selected by `DATABASE_URL` env var: Postgres if set, else SQLite default

---

### T3.2 — Route implementations

- [ ] Create `apps/api/routes/session.py`
  - `POST /api/session` — creates session, returns `{ session_id, mode }`
  - `POST /api/session/:id/delete` — calls `delete_session`, returns verified counts
- [ ] Create `apps/api/routes/document.py`
  - `POST /api/session/:id/document` — multipart upload
  - Validates: MIME sniff, magic bytes, page count 1–100
  - Scanned PDF detection: `pdfplumber` extracts zero chars on all pages → 422 with correct message
  - In fixture mode: ignores upload, returns fixture document metadata
- [ ] Create `apps/api/routes/clauses.py`
  - `GET /api/session/:id/clauses` → `Clause[]`
  - `PATCH /api/session/:id/clauses/:cid` — updates status, validates new status is legal
- [ ] Create `apps/api/routes/simulate.py`
  - `POST /api/session/:id/simulate` — calls `simulate_claim`, asserts invariants, persists run
  - If `invariants_ok == False`: returns 500 with hard error, never returns the bad result
  - `POST /api/session/:id/counterfactual` — calls `counterfactual`, returns delta
- [ ] Create `apps/api/routes/plan.py`
  - `GET /api/session/:id/loans` — computes `LoanMetrics[]` from fixture `loan_offers.json` + session affordability context
  - `GET /api/session/:id/plan` — returns `ActionStep[]` from deterministic server-side rules (not LLM)
  - Plan steps are derived from: which material facts are unconfirmed, room cap status, loan lean-month status

- [ ] Create `apps/api/main.py`
  - Mount all routers
  - CORS configured for local dev
  - Global error handler: all exceptions mapped to typed error shape

---

### T3.3 — API integration smoke test

- [ ] Manually verify (or via a `pytest` fixture test) that the full sequence works:
  1. `POST /api/session` with `use_fixture: true`
  2. `GET /api/session/:id/clauses` returns 4+ clauses
  3. `PATCH` room-limit clause to `user_confirmed`
  4. `POST /api/session/:id/simulate` returns `insurer_payment = 81333` for scenario B
  5. `POST /api/session/:id/counterfactual` with room change returns `delta = 29167`
  6. `GET /api/session/:id/loans` returns 3 offers, all with negative `free_cash_lean_month`
  7. `GET /api/session/:id/plan` returns 4 steps
  8. `POST /api/session/:id/delete` returns `deleted: true` with counts > 0

**G3 exit command:** `pnpm test:api` green; API smoke test passes end-to-end

---

## Gate G4 — Screens 1–3

**Exit condition:** Demo journey reaches Screen 3, toggles produce `₹38,667 ↔ ₹9,500`, and the e2e spec passes for screens 1–3.

---

### T4.1 — Next.js project setup

- [ ] Initialise Next.js 15 App Router in `apps/web/`
- [ ] Configure `tsconfig.json`: `strict: true`, `noImplicitAny`, `strictNullChecks`, `noUncheckedIndexedAccess`
- [ ] Configure Tailwind CSS with custom design tokens matching `styles/tokens.css`
- [ ] Self-host IBM Plex Sans, IBM Plex Sans Devanagari, IBM Plex Mono via `next/font`
  - Weights: 400 and 500 only
  - No other font loaded
- [ ] Create `styles/tokens.css` with all CSS custom properties from design.md §7.5
- [ ] Verify: `pnpm --filter web build` exits 0 on empty shell

---

### T4.2 — Shared utilities

- [ ] Create `apps/web/lib/format.ts`
  - `formatINR(amount: number): string` — uses `Intl.NumberFormat('en-IN')`, returns `"₹1,20,000"`
  - `formatINRDense(amount: number): string` — returns `"1.2L"`
  - `formatDelta(amount: number): string` — uses U+2212 for negative, returns `"−₹29,167"`
  - `formatPct(rate: number, dp?: number): string` — always appends `" p.a."` for rates
  - All functions are pure, no side effects
  - Unit tests via Vitest: `formatINR(120000) === "₹1,20,000"` etc.

- [ ] Create `apps/web/lib/api.ts`
  - Typed fetch wrappers for all API endpoints
  - Returns typed responses (matching TypeScript interfaces from design.md §3.5)
  - No `any`, no non-null assertions
  - Error responses throw typed `ApiError` with `error`, `message`, `code`

- [ ] Create `apps/web/lib/i18n.ts`
  - `Lang = "en" | "hi"` type
  - Flat string table for all UI strings in both languages
  - `t(key: string, lang: Lang): string` — throws (compile-time via typed keys) if key missing

---

### T4.3 — Shared components

- [ ] Create `apps/web/components/StatusDot.tsx`
  - Props: `status: ClauseStatus`, `label: string`
  - 6×6px square (`border-radius: 2px`), colour from token map
  - `synthetic` status: outlined (transparent fill)
  - 11px uppercase label always present — never colour alone
  - No circle. No rounded dots.

- [ ] Create `apps/web/components/VerdictBar.tsx`
  - Sticky bottom, full-width, 1px top border `--color-border`, shadow `--shadow-modal`
  - Left: "You pay" + formatted amount
  - Right: action button
  - `aria-live="polite"` on amount `<span>`
  - 240ms count animation on value change
  - 600ms background flash on the changed waterfall row (`rgba(11,93,82,0.08)` → transparent)
  - Both animations disabled by `prefers-reduced-motion`
  - No other motion anywhere in the app

- [ ] Create `apps/web/components/WaterfallTable.tsx`
  - Plain `<table>` — no CSS framework component
  - Label left, amount right, tabular numerals, `text-align: right` on amount column
  - Deduction rows: `−` prefix
  - Each deduction row: `<button>?</button>` that reveals `basis` text inline
  - Final row: `border-top: 2px solid`, `font-weight: 500`
  - Every amount passed as `WithStatus<number>` — compile-time error if status absent

- [ ] Create `apps/web/components/ClauseRow.tsx`
  - Collapsed: name, value, page ref, `<StatusDot>`
  - Expanded: `<blockquote>` (13px, `border-left: 2px solid var(--color-border)`), rule, three `<button>`s
  - No animation on expand/collapse

- [ ] Create `apps/web/components/ConsentBlock.tsx`
  - Collapsed to one line with `▾` toggle
  - Expanded: 4-row `<table>` — purpose, documents, retention, what we don't do

- [ ] Create `apps/web/components/TogglePanel.tsx`
  - Three controls: room toggle, continuity toggle, bill numeric input
  - Tracks `changedCount` since baseline
  - If `changedCount > 1`: shows "N things changed — we can't attribute this to one clause"
  - Otherwise: calls `/simulate` on change, surfaces `DeltaChip`

- [ ] Create `apps/web/components/DeltaChip.tsx`
  - Amount in `--color-conflict` (`#A8322D`), 12px, tabular, U+2212
  - One sentence with clause reference
  - `<button>` wrapper — click opens clause

- [ ] Create `apps/web/components/EvidenceViewer.tsx`
  - Renders policy page text (not an image)
  - Highlighted span: `background: #FBF3D9`, `border-bottom: 2px solid #B4762A`
  - No glow, no pulse
  - On clause selection: scroll to highlighted span

---

### T4.4 — Screen 1: Goal (`app/page.tsx`)

- [ ] H1 at 26px/500: "What are you planning for?"
- [ ] Three radio cards (real `<input type="radio">` + `<label>`): full-width, 44px+ tall, hairline border, selected = 2px `--color-brand` border + tick (text character, not emoji)
- [ ] Free-text `<textarea>`: label "Or describe it in your own words", placeholder in English and Hinglish
- [ ] `<ConsentBlock>` collapsed by default
- [ ] "Use sample data" toggle, on by default, labelled as per spec
- [ ] `<button>` "Start →" — calls `POST /api/session`, routes to `/evidence/:id`
- [ ] No feature grid, no marketing copy, no illustration, no gradient, no hero section
- [ ] Max content width 560px, left-aligned
- [ ] Fixture mode banner if sample data is on: `"Sample data · a fictional policy and bill. Calculations are live."` in `--color-caution` on `--color-fixture-bg`. Never dismissible.

---

### T4.5 — Screen 2: Policy (`app/evidence/[sessionId]/page.tsx`)

- [ ] Document header row: filename, page count, "Replace" link; fixture mode text as specified
- [ ] Unconfirmed facts banner (if any material fact unconfirmed): count + "Review" anchor
- [ ] `<EvidenceViewer>` — left pane desktop, slide-over mobile
- [ ] `<ClauseRow>` list grouped by: Coverage · Waiting periods · Limits · Exclusions
- [ ] Material rows (room limit, waiting period, non-payables, apportionment base) carry required-action marker
- [ ] Sticky bottom button "See what you'll pay →" disabled until all 4 material facts resolved
- [ ] Disabled button shows reason: "Confirm or mark unknown: [list of unresolved facts]"
- [ ] Mobile: clause list full-width, tap opens evidence slide-over (no animation, use CSS)

---

### T4.6 — Screen 3: Simulate (`app/simulate/[sessionId]/page.tsx`)

- [ ] "Your out-of-pocket" label, amount at 34px/500 tabular, plain comparison sentence
- [ ] If any `unresolved`: range display `₹9,500 – ₹38,667` + one-sentence clause link
- [ ] `<WaterfallTable>` with all deductions expandable
- [ ] `<TogglePanel>` with three controls (room, continuity, bill)
- [ ] `<DeltaChip>` appears on single-field change; suppressed on multi-field change
- [ ] `<VerdictBar>` sticky, animates on change
- [ ] Savings/gap section: plain text (no card, no styled box) — "Savings cover ₹35,000. Gap to fund: ₹85,000."
- [ ] `<LoanTable>` — plain `<table>`, labelled synthetic
- [ ] `<LeanMonthBar>` component with caption

- [ ] Create `apps/web/components/LoanTable.tsx`
  - Plain `<table>` — no component library
  - Columns: Offer, EMI, APR nominal, APR effective, Lean month free cash
  - APR shown as "X.XX% p.a." — both nominal and effective, neither labelled "interest rate"
  - "Synthetic offers — illustrative only" caption above table

- [ ] Create `apps/web/components/LeanMonthBar.tsx`
  - Horizontal bar, range −₹6,000 to +₹10,000
  - Three labelled markers (A, B, C), all left of zero in fixture
  - Zero line visible
  - Caption below (plain text): "None of these loans is serviceable in your worst month."
  - No chart library over 40kB; implement as a simple SVG or CSS position-based component

---

### T4.7 — E2E test — screens 1–3

- [ ] Create `e2e/demo.spec.ts`
  - Open `/`, select "A hospital procedure", enable sample data, click "Start"
  - Wait for redirect to `/evidence/:id`
  - Assert fixture banner is visible
  - Confirm all 4 material facts (mock user interactions)
  - Click "See what you'll pay →"
  - Wait for `/simulate/:id`
  - Assert `data-testid="oop"` has text `"₹38,667"` (scenario B)
  - Toggle room to "At cap" — assert `data-testid="oop"` changes to `"₹9,500"`
  - Assert `DeltaChip` shows `"−₹29,167"`
  - Toggle back — assert returns to `"₹38,667"`
  - Toggle continuity to "Unconfirmed" — assert transitions to `"₹1,20,000"`
  - Toggle both room and continuity — assert multi-change message appears, no DeltaChip

**G4 exit command:** `pnpm test:e2e` passes screens 1–3 assertions; `pnpm build` exits 0

---

## Gate G5 — Screens 4–5

**Exit condition:** Action plan and Delete flow work; e2e covers all 5 screens.

---

### T5.1 — Screen 4: Plan (`app/plan/[sessionId]/page.tsx`)

- [ ] Four ranked `<ActionStep>` items from server `GET /plan` response (not LLM)
  - Each: rank number, title, "why" sentence with rupee figure, effort label, "See the clause →" link
  - Step 1: continuity credit, ₹81,333
  - Step 2: room at cap, ₹29,167
  - Step 3: apportionment confirmation, up to ₹24,667
  - Step 4: loan warning (Offer A and C negative lean month)
- [ ] Draft insurer message: `<textarea>` pre-filled with GRO template (referencing Bima Bharosa, 14-day window)
- [ ] "Copy" `<button>` (uses `navigator.clipboard.writeText`)
- [ ] Label above textarea: "This is a draft. Check every figure before you send it."
- [ ] Unresolved evidence section: list of `unknown` and `conflicting` clauses
- [ ] Footer disclaimer (11px, `--color-text-3`): "These are modelled estimates, not claim decisions. Dhaal does not guarantee any claim outcome."
- [ ] "View your data and delete →" button → `/audit/:id`

---

### T5.2 — Screen 5: Audit (`app/audit/[sessionId]/page.tsx`)

- [ ] Data usage `<table>`: document, purpose, pages read, retention status
- [ ] Engine transparency block: version string, run hash, reproducibility statement
- [ ] AI disclosure: what was sent to a provider, or "Nothing — fixture mode"
- [ ] Delete button: `<button>` styled with `--color-conflict`, opens confirmation modal
  - Modal requires typing `DELETE` in an `<input>` before the confirm button enables
  - On confirm: calls `POST /api/session/:id/delete`, shows verified counts
  - Modal has `role="dialog"`, `aria-modal="true"`, focus trapped inside
- [ ] Language toggle: "English / हिंदी" — updates `?lang=` param and `<html lang>` attribute

---

### T5.3 — E2E test — screens 4–5

- [ ] Continue e2e spec from G4:
  - Navigate to `/plan/:id`
  - Assert first action step contains "₹81,333"
  - Assert GRO template text is present in textarea
  - Click "View your data and delete →"
  - Navigate to `/audit/:id`
  - Assert engine version is present
  - Open Delete modal, type "DELETE", click confirm
  - Assert response shows `documents: 1`, `clauses` > 0, `runs` > 0
  - Assert page shows deletion confirmed message

**G5 exit command:** `pnpm test:e2e` passes all five screens; `pnpm build` exits 0

---

## Gate G6 — Design Audit

**Exit condition:** Every item in §9.1 of the product spec is absent from the codebase. Every requirement in §9.2–9.3 is present and verified.

---

### T6.1 — Forbidden pattern audit

Read §9.1 of the product spec line by line and verify each item is absent:

- [ ] No purple/indigo/violet anywhere (search all `.css`, `.tsx` files)
- [ ] No `backdrop-blur`, `frosted`, or translucent panels
- [ ] No `box-shadow` with large spread or `rgba` glow values (only `--shadow-modal` is permitted)
- [ ] No emoji in headings or as icons
- [ ] No sparkle/wand/AI-magic icons or "Powered by AI" text
- [ ] No `bg-clip-text` gradient text
- [ ] No `rounded-3xl` or `rounded-2xl` anywhere
- [ ] No feature-card grid (icon + heading + one-liner + link, repeated 3–6 times)
- [ ] No centered hero section with large headline and subtitle
- [ ] No stock illustrations, blob shapes, isometric art, mesh backgrounds
- [ ] No Lottie or looping animation
- [ ] No coloured pill/badge wrapping every label
- [ ] No avatar with gradient ring
- [ ] No glassy sidebar with glow
- [ ] No dashboard with 4 identical KPI cards
- [ ] No viewport with a single short sentence and excessive whitespace
- [ ] No marketing verbs ("Supercharge", "Unlock", "Empower", "Seamless", "Revolutionise")

---

### T6.2 — Required design details audit

- [ ] IBM Plex Sans loaded, Inter not loaded (check `next/font` imports)
- [ ] `font-variant-numeric: tabular-nums` on every element that renders a monetary figure (search for `formatINR` call sites)
- [ ] `formatINR(120000) === "₹1,20,000"` — run the Vitest test
- [ ] Negative amounts use U+2212 (`−`) not hyphen — check `formatDelta` output
- [ ] Base font size 14px in `globals.css`
- [ ] No font weight 600 or 700 except the single 26px page title
- [ ] Border-radius: no value above 8px anywhere
- [ ] Exactly one shadow definition used in exactly two places (modal + VerdictBar)
- [ ] Exactly two animations defined; both gated on `prefers-reduced-motion`
- [ ] Money columns right-aligned in all tables
- [ ] Every status dot is a square (6×6px, `border-radius: 2px`), not a circle
- [ ] All tap targets ≥ 44×44px (check interactive elements on Screen 1 radio cards, Screen 2 clause rows)
- [ ] Focus rings: `2px solid #1F4E79, outline-offset: 2px` on all interactive elements; `outline: none` absent
- [ ] Fixture mode banner always visible and never dismissible when `mode === "fixture"`
- [ ] APR columns show both nominal and effective; neither labelled "interest rate"
- [ ] `<LeanMonthBar>` caption says "None of these loans is serviceable in your worst month" — not softened

---

### T6.3 — No monetary literals in frontend

- [ ] Search all `.tsx` files for hardcoded rupee values (regex: `₹\d`, `\d{4,}`) — zero hits except inside string-table `i18n.ts` for labels that are not amounts
- [ ] Every figure on screen originates from `ClaimResult`, `LoanMetrics`, or `AffordabilitySummary` from the API

**G6 exit command:** All checklist items above confirmed; `pnpm lint` exits 0

---

## Gate G7 — Hardening

**Exit condition:** Network-off demo works; injection tests pass; no PII in logs.

---

### T7.1 — Offline / fixture mode

- [ ] Disconnect network (or set env to no API keys)
- [ ] Run full five-screen demo manually: start → evidence → simulate → plan → audit → delete
- [ ] All five screens render, all figures match golden values
- [ ] Fixture banner visible on every screen
- [ ] No network errors in browser console

---

### T7.2 — Injection hardening

- [ ] Confirm `check_injection` is called before any document text reaches the extraction provider
- [ ] Quarantined documents route to manual entry form, not to the extraction pipeline
- [ ] Add test: upload a PDF containing "ignore previous instructions" → assert `quarantined` status returned

---

### T7.3 — PII audit

- [ ] Review all logging calls in `apps/api/` — no document text, no session IDs in plain text, no filenames
- [ ] AI provider calls: confirm the request body does not contain policy numbers or proper nouns
- [ ] Confirm `.env` is in `.gitignore` and not staged in git

---

### T7.4 — Edge case hardening

- [ ] Upload a scanned PDF (image-only): assert 422 with `"scanned_pdf"` error code and exact user message
- [ ] Upload a non-PDF: assert 422 with typed error
- [ ] Upload a PDF > 10MB: assert 413
- [ ] Call `/simulate` with `invariants_ok = false` scenario: assert 500, result never rendered in frontend

**G7 exit command:** Manual offline demo succeeds; `pnpm test:api` green (including injection test)

---

## Gate G8 — Final

**Exit condition:** All items in §15 (Definition of Done) of the product spec are verified by running the listed commands.

---

### T8.1 — Build clean

- [ ] `pnpm build` exits 0 with no warnings
- [ ] No TypeScript errors (`tsc --noEmit`)
- [ ] No Python type errors (`mypy --strict apps/api/`)
- [ ] `pnpm lint` exits 0

---

### T8.2 — Full test suite

- [ ] `pnpm test:api` — all golden values to 2dp, all property tests pass
- [ ] `pnpm test:e2e` — full five-screen journey, all exact rupee figures asserted

---

### T8.3 — Accessibility

- [ ] Lighthouse a11y audit ≥ 95 (run `pnpm --filter web exec lighthouse`)
- [ ] 360px viewport: no horizontal scroll on any of the five screens
- [ ] 1440px viewport: two-pane layout correct on screens 2 and 3
- [ ] 200% browser zoom: no clipping
- [ ] Keyboard-only: tab through all five screens, reach every interactive element
- [ ] Screen reader: `aria-live` on VerdictBar announces value change

---

### T8.4 — Definition of Done checklist

Work through §15 of the product spec one item at a time:

- [ ] `pnpm build` exits 0, no warnings
- [ ] `pnpm test:api` passes every golden value to 2dp
- [ ] `pnpm test:e2e` completes five-screen journey with exact figures
- [ ] Network disabled → full demo runs end-to-end
- [ ] Toggling room → ₹38,667 to ₹9,500, DeltaChip shows `−₹29,167` with clause name
- [ ] Toggling continuity → ₹1,20,000 to ₹38,667, DeltaChip shows `₹81,333`
- [ ] Waterfall final row: `insurer + you == gross` verified at runtime
- [ ] Zero rupee literals in any `.tsx` file (grep confirms)
- [ ] Zero items from §9.1 present in codebase (grep confirms)
- [ ] `formatINR(120000) === "₹1,20,000"` (Vitest confirms)
- [ ] Every monetary figure uses `tabular-nums`
- [ ] Every displayed figure carries a status label
- [ ] All three loan cards show negative lean-month balance
- [ ] Delete removes document, clauses, runs; returns verified counts
- [ ] Works at 360px, no horizontal scroll
- [ ] Keyboard-only navigation reaches every action
- [ ] No API key in repo; `.env.example` present with placeholders
- [ ] README documents: setup, run, test, fixture mode, known limitations

---

### T8.5 — README

- [ ] Create `README.md` at repo root covering:
  - Prerequisites (Node, pnpm, Python 3.11+)
  - Setup: `pnpm install` + Python venv + `pip install -e apps/api`
  - Run: `pnpm dev` (both processes)
  - Test: `pnpm test:api`, `pnpm test:e2e`
  - Fixture mode: how to use with no API key
  - Known limitations: scanned PDFs not supported; APR bisection assumes fixed payments; no multi-policy support

**G8 exit command:** All items in §15 confirmed by running the listed commands. Build is done.

---

## Summary Table

| Gate | What ships | Key exit command |
|------|-----------|-----------------|
| G1 | Financial engine + all tests | `pnpm test:api` — zero failures |
| G2 | Evidence schema, verifier, fixture provider, fixture files | `pnpm test:api` includes `test_verify.py` |
| G3 | API routes wired to engine and evidence | API smoke test end-to-end |
| G4 | Screens 1–3; toggle produces ₹38,667 ↔ ₹9,500 | `pnpm test:e2e` screens 1–3 |
| G5 | Screens 4–5; Delete works with verified counts | `pnpm test:e2e` all 5 screens |
| G6 | Design audit; zero §9.1 violations; all §9.2–9.3 present | Manual + grep audit |
| G7 | Offline demo; injection tests; PII clean | Manual offline + `pnpm test:api` |
| G8 | Final build clean; §15 definition of done | `pnpm build` + `pnpm test:api` + `pnpm test:e2e` |
