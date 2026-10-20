# ढाल DHAAL

An evidence-linked financial consequence engine for Indian households facing a
**planned** hospitalisation. DHAAL turns a health-insurance policy's clauses and a
hospital's bill estimate into a reproducible, conditional estimate of what the
patient would pay — with every figure traceable to a quoted source.

DHAAL is **not** affiliated with any insurer, never predicts claim approval, and
never invents policy terms. Anything it cannot verify from the policy wording is
shown as a range or an explicit unknown — never a silently defaulted number.

## Policy-first design

Every calculation is grounded in **the user's own policy**, identified before
anything is simulated:

1. **Identify the exact policy.** Search the catalogue of policy wordings
   DHAAL actually holds (autocomplete by insurer/product), pick the exact
   version when several are held, or upload your own policy PDF. Nothing is
   auto-selected, and a policy DHAAL cannot verify is never substituted with
   a look-alike — you are asked for your PDF instead.
2. **Provenance is recorded.** The document used is stored with its source
   (held wording vs your upload), version, effective date, SHA-256 of the
   exact bytes, and retrieval time — visible on the review and audit screens.
3. **Review your policy conditions.** The clauses that move money are shown
   with a plain-language reading, the exact quoted wording, section and page,
   character offsets, and verification status: room-rent limit, proportionate
   deduction, initial / specified-disease / pre-existing waiting periods,
   permanent exclusions, non-payable items, co-payment, deductible. You
   confirm, correct, or mark each one unknown. Nothing is simulated until
   every material clause is decided; conflicting clauses stop the simulation
   and ask for review.
4. **Claim facts are never guessed.** Waiting periods apply only to the
   diseases/procedures the wording lists, computed from the actual inception
   and admission dates (plus any evidenced continuity/portability credit).
   If the condition, pre-existing status, or dates are unknown, the affected
   rules are reported as unresolved and widen the result range instead of
   being applied.
5. **Every deduction traces to a clause.** The deterministic waterfall cites
   the source clause (page and section) for every rupee deducted — there is
   no policy-specific deduction without a verified source clause or an
   explicitly user-provided policy document.

The shipped catalogue contains only wordings actually held locally (clearly
labelled fictional sample policies, with extractable PDFs and clause files
under `fixtures/`). Real insurer products are never seeded from memory: to
add a real wording, place the verified document in `fixtures/`, extract its
clauses with quoted evidence, and register it in
`fixtures/policy_catalogue.json` (see `fixtures/build_policy_fixtures.py`
for how the sample wordings were generated and verified).

## What it does

1. **Goal + policy** — you say what you are planning for, then find your
   exact policy (or upload your PDF / try the fictional sample).
2. **Review conditions** — clauses beside the document text that proves
   them, with plain-language explanations and the simulate gate.
3. **What you'll pay** — claim facts form, then a waterfall from the gross
   bill to the insurer/patient split, one-change-at-a-time scenarios (room
   within cap? continuity credit? different bill?) with the rupee effect of
   each single change and the clause behind it. Unresolved interpretations
   produce a range, labelled as an estimate — never as an approved
   settlement.
4. **What to do** — action steps ranked by engine-computed rupee value, plus
   an editable draft message to the insurer. Nothing is sent anywhere.
5. **Your data** — what the session holds, the policy simulated and its
   document provenance, the calculation record (engine version, extraction
   provider, per-run hashes), and one-click deletion.

## Quickstart

Prerequisites: Python 3.11+, Node 20+, pnpm 9 (`npm i -g pnpm@9`).

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -e "apps/api[dev]"

# Frontend
pnpm install

# Run both (API on :8000, web on :3000) — keep the venv activated so the
# api workspace script can find `uvicorn`:
source .venv/bin/activate
pnpm dev
```

`pnpm dev` runs the API (`uvicorn main:app`, working directory `apps/api`) and
the Next.js dev server together. The web app proxies `/api/*` to the API
(`API_INTERNAL_URL`, default `http://127.0.0.1:8000`).

Open <http://localhost:3000> and press **Start →** (the sample policy is the
default; or use **Find my policy** to pick a different held wording). The
demo runs entirely on fictional fixtures — **no API credentials needed**.

### Demo walkthrough

1. **Review screen.** Six of the sample policy's seven clauses are verified
   against the PDF text; the *proportionate deduction* clause is flagged
   unresolved because the wording does not say which expenses the deduction
   applies to. Confirm it as-is (keeps the ambiguity) or use **Correct** to
   pick an interpretation. The header shows exactly which wording (product,
   version, SHA-256) is being simulated.
2. **Simulation screen.** Because the deduction base is unresolved, your
   out-of-pocket is a **range — ₹14,000 to ₹38,667** on the ₹1,20,000 sample
   bill (point estimate ₹14,000; insurer ₹1,06,000). The range only spans
   readings the policy wording supports: the clause expressly exempts
   medicines, so an all-expenses reading is never used as the ceiling.
   Toggle the room to within the ₹3,000/day cap and watch it become ₹9,500
   (non-payables only). Change the claim facts — condition, dates,
   pre-existing flag — and watch the scoped waiting periods apply or fall
   away per the wording.
3. **Try another policy.** Start over, choose **Find my policy**, and select
   *AarogyaKavach Prime (2022)* or *Suraksha Shield Health (2024)*. The same
   bill produces a different, clause-traced result (fixed room caps, a 10%
   co-payment, and a ₹5,000 deductible under AarogyaKavach) — because the
   rules come from the selected wording, not from defaults.
