/**
 * Typed API client for the DHAAL backend.
 *
 * Decimal values travel as strings end-to-end; nothing here converts them
 * to numbers (formatting does that at render time via lib/format.ts).
 * All calls are same-origin (/api/*) — Next.js proxies to FastAPI.
 */

export type ClauseStatus =
  | "verified"
  | "unverified"
  | "unknown"
  | "conflicting"
  | "user_confirmed"
  | "synthetic";

export type Mode = "fixture" | "live";

export class ApiError extends Error {
  readonly code: number;
  readonly apiError: string;

  constructor(code: number, apiError: string, message: string) {
    super(message);
    this.code = code;
    this.apiError = apiError;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server. Please try again.");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let apiError = "http_error";
    try {
      const body: unknown = await res.json();
      if (typeof body === "object" && body !== null) {
        const rec = body as Record<string, unknown>;
        if (typeof rec["detail"] === "string") message = rec["detail"];
        else if (typeof rec["message"] === "string") message = rec["message"];
        if (typeof rec["error"] === "string") apiError = rec["error"];
      }
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, apiError, message);
  }
  return (await res.json()) as T;
}

/* ------------------------------- Session ------------------------------- */

export interface SessionCreated {
  session_id: string;
  mode: Mode;
}

export interface MaterialFactState {
  rule_type: string;
  status: string; // ClauseStatus or "missing"
}

export interface SessionDetail {
  session_id: string;
  mode: Mode;
  goal: string | null;
  created_at: string;
  has_document: boolean;
  simulation_ready: boolean;
  material_facts: MaterialFactState[];
}

export interface DeleteResult {
  deleted: boolean;
  verified: boolean;
  counts: Record<string, number>;
}

export function createSession(useFixture: boolean, goal: string): Promise<SessionCreated> {
  return request<SessionCreated>("/api/session", {
    method: "POST",
    body: JSON.stringify({ use_fixture: useFixture, goal }),
  });
}

export function getSession(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/session/${sessionId}`);
}

export function deleteSession(sessionId: string): Promise<DeleteResult> {
  return request<DeleteResult>(`/api/session/${sessionId}/delete`, { method: "POST" });
}

/* ------------------------------ Document ------------------------------- */

export interface DocumentInfo {
  document_id: string;
  filename: string;
  page_count: number;
  mode: Mode;
}

export interface DocumentPages {
  document_id: string;
  filename: string;
  page_count: number;
  pages: string[];
}

/**
 * Upload a policy PDF. In fixture mode the backend ignores the file and
 * loads the built-in fictional policy — the frontend still must make the
 * call to trigger document + clause creation.
 */
export async function uploadDocument(sessionId: string, file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/session/${sessionId}/document`, {
    method: "POST",
    body: form,
    cache: "no-store",
  });
  if (!res.ok) {
    let message = `Upload failed (${res.status})`;
    try {
      const body: unknown = await res.json();
      if (typeof body === "object" && body !== null) {
        const rec = body as Record<string, unknown>;
        if (typeof rec["detail"] === "string") message = rec["detail"];
      }
    } catch {
      // keep generic message
    }
    throw new ApiError(res.status, "upload_error", message);
  }
  return (await res.json()) as DocumentInfo;
}

/** Empty upload used to trigger fixture-document loading. */
export function loadFixtureDocument(sessionId: string): Promise<DocumentInfo> {
  const empty = new File(["%PDF"], "policy.pdf", { type: "application/pdf" });
  return uploadDocument(sessionId, empty);
}

export function getDocumentPages(sessionId: string): Promise<DocumentPages> {
  return request<DocumentPages>(`/api/session/${sessionId}/document`);
}

/* ------------------------------- Clauses ------------------------------- */

export interface Verification {
  schema_valid: boolean;
  quote_found: boolean;
  numbers_supported: boolean;
  interpretation_status: ClauseStatus;
  reason: string;
}

export interface Clause {
  clause_id: string;
  document_id: string;
  page: number | null;
  char_start: number | null;
  char_end: number | null;
  quote: string | null;
  quote_hash: string | null;
  rule: { type: string; params: Record<string, string> };
  verification: Verification;
}

export function getClauses(sessionId: string): Promise<Clause[]> {
  return request<Clause[]>(`/api/session/${sessionId}/clauses`);
}

export function patchClause(
  sessionId: string,
  clauseId: string,
  status: "user_confirmed" | "unknown",
  override?: { rule_params: Record<string, string> },
): Promise<Clause> {
  return request<Clause>(`/api/session/${sessionId}/clauses/${clauseId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, override: override ?? null }),
  });
}

/* ------------------------------ Estimate ------------------------------- */

export interface ChargeItemInput {
  name: string;
  amount: string;
  nights: number | null;
}

export interface Affordability {
  months: string[];
  month_labels: string[];
  mean_income: string;
  median_income: string;
  lowest_income: string;
  avg_free_cash: string;
  lean_free_cash: string;
  emergency_runway_months: string;
  obligations_at_lean_pct: string;
  savings: string;
  essentials: string;
  existing_emi: string;
  synthetic: boolean;
}

export interface Estimate {
  gross_bill: string;
  nights: number;
  room_rate_per_night: string;
  charges: ChargeItemInput[];
  non_payable_total: string;
  hospital_name: string;
  procedure: string;
  admission_date: string;
  discharge_date: string;
  sum_insured: string;
  policy_month_at_admit: number;
  room_cap_per_day: string | null;
  waiting_months_required: number | null;
  affordability: Affordability;
  synthetic: boolean;
}

export function getEstimate(sessionId: string): Promise<Estimate> {
  return request<Estimate>(`/api/session/${sessionId}/estimate`);
}

/* ----------------------------- Simulation ------------------------------ */

export interface SimulationAssumptions {
  policy_month_at_admit: number;
  remaining_sum_insured: string;
  sum_insured: string;
  non_payable_total: string | null;
  apportionment_base: string;
  continuity_confirmed: boolean;
}

export interface SimulateRequest {
  gross: string;
  charges: ChargeItemInput[];
  room_rate_per_night: string;
  nights: number;
  assumptions: SimulationAssumptions;
}

export interface Deduction {
  name: string;
  amount: string;
  basis: string;
  rule_id: string;
  citation: string;
}

export interface UnresolvedRule {
  rule_type: string;
  reason: string;
  low_impact: string;
  high_impact: string;
}

export interface ClaimResult {
  gross_bill: string;
  non_payable_total: string;
  admissible: string;
  deductions: Deduction[];
  insurer_payment: string;
  out_of_pocket: string;
  remaining_sum_insured: string;
  unresolved: UnresolvedRule[];
  range_low: string | null;
  range_high: string | null;
  invariants_ok: boolean;
}

export interface CounterfactualResult {
  result: ClaimResult;
  delta: string;
  oop_delta: string;
  changed_fields: string[];
  interaction_residual: string;
}

export function simulate(sessionId: string, body: SimulateRequest): Promise<ClaimResult> {
  return request<ClaimResult>(`/api/session/${sessionId}/simulate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function counterfactual(
  sessionId: string,
  base: SimulateRequest,
  change: { field: string; from_val: string | number; to_val: string | number },
): Promise<CounterfactualResult> {
  return request<CounterfactualResult>(`/api/session/${sessionId}/counterfactual`, {
    method: "POST",
    body: JSON.stringify({ base, change }),
  });
}

/* -------------------------------- Loans -------------------------------- */

export interface LoanMetrics {
  label: string;
  principal: string;
  emi: string;
  net_disbursed: string;
  total_repayment: string;
  total_interest: string;
  total_cash_out: string;
  apr_nominal: string;
  apr_effective: string;
  emi_pct_of_mean: string;
  emi_pct_of_lean: string;
  free_cash_avg_month: string;
  free_cash_lean_month: string;
  synthetic: boolean;
}

export function getLoans(sessionId: string): Promise<LoanMetrics[]> {
  return request<LoanMetrics[]>(`/api/session/${sessionId}/loans`);
}

/* --------------------------------- Plan -------------------------------- */

export interface ActionStep {
  rank: number;
  title: string;
  why: string;
  effort: string;
  clause_id: string | null;
  rupee_value: string;
}

export interface Plan {
  steps: ActionStep[];
  draft_message: string;
  unresolved_items: string[];
}

export function getPlan(sessionId: string): Promise<Plan> {
  return request<Plan>(`/api/session/${sessionId}/plan`);
}

/* -------------------------------- Audit -------------------------------- */

export interface AuditRun {
  run_id: string;
  created_at: string;
  run_hash: string;
  invariants_ok: boolean;
  insurer_payment: string | null;
  out_of_pocket: string | null;
}

export interface Audit {
  session_id: string;
  mode: Mode;
  document: {
    filename: string;
    page_count: number;
    pages_read: number;
    retention: string;
  } | null;
  engine_version: string;
  provider_name: string;
  provider_disclosure: string;
  runs: AuditRun[];
  clauses_by_status: Record<string, number>;
}

export function getAudit(sessionId: string): Promise<Audit> {
  return request<Audit>(`/api/session/${sessionId}/audit`);
}
