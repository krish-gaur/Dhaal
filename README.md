# ढाल DHAAL

An evidence-linked financial consequence engine for Indian households facing a
**planned** hospitalisation. DHAAL turns a health-insurance policy's clauses and a
hospital's bill estimate into a reproducible, conditional estimate of what the
patient would pay — with every figure traceable to a quoted source.

DHAAL is **not** affiliated with any insurer, never predicts claim approval, and
never invents policy terms. Anything it cannot verify from the policy wording is
shown as a range or an explicit unknown — never a silently defaulted number.

## What it does

1. **Goal** — you say what you are planning for, and give a policy PDF (or use the
   built-in fictional sample).
2. **Evidence** — the clauses that move money (room-rent limit, proportionate
   deduction base, waiting period, non-payable items) are shown with the exact
   quoted wording, page, and character offsets. You confirm, correct, or mark
   each one unknown. Nothing is simulated until every material clause is decided.
3. **What you'll pay** — a waterfall from the gross bill to the insurer/patient
   split, then one-change-at-a-time scenarios (room within cap? continuity
   credit? different bill?) with the rupee effect of each single change and the
   clause behind it. If a rule's interpretation is unresolved, you get a range.
4. **What to do** — action steps ranked by engine-computed rupee value, plus an
   editable draft message to the insurer. Nothing is sent anywhere.
5. **Your data** — what the session holds, the calculation record (engine
   version, extraction provider, per-run hashes), and one-click deletion.

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

Open <http://localhost:3000>, keep “Use sample data” on, and press **Start →**.
The demo runs entirely on fictional fixtures — **no API credentials needed**.

### Demo walkthrough

1. **Evidence screen.** Three clauses are verified against the PDF text; the
   *proportionate deduction* clause is flagged unresolved because the wording
   does not say which expenses the deduction applies to. Confirm it as-is
   (keeps the ambiguity) or use **Correct** to pick an interpretation.
2. **Simulation screen.** Because the deduction base is unresolved, your
   out-of-pocket is a **range — ₹14,000 to ₹38,667** on the ₹1,20,000 sample
   bill (point estimate ₹14,000; insurer ₹1,06,000). The range only spans
   readings the policy wording supports: the clause expressly exempts
   medicines, so an all-expenses reading is never used as the ceiling. Toggle the room to within
   the ₹3,000/day cap and watch it become ₹9
...[truncated 2248 chars]