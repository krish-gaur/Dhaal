/**
 * Scenario state for Screen 3 and translation into API requests.
 *
 * This module only assembles *inputs*. Every calculation result (amounts,
 * deductions, deltas) comes from the backend engine.
 */

import type { ChargeItemInput, Clause, ClauseStatus, Estimate, SimulateRequest } from "./api";
import { dec } from "./format";

export interface ScenarioState {
  roomAtCap: boolean;
  continuityConfirmed: boolean;
  grossBill: string; // Decimal string — the bill-amount control
}

/**
 * The claim facts the engine needs before any scoped waiting period or
 * exclusion may apply. "unsure" values travel as null and surface as
 * unresolved — they are never silently defaulted.
 */
export interface ClaimState {
  conditionTag: string | null;
  preExisting: boolean | null;
  accident: boolean;
  inceptionDate: string | null; // YYYY-MM-DD
  admissionDate: string | null; // YYYY-MM-DD
  continuityCreditMonths: number;
}

export function baselineClaim(estimate: Estimate): ClaimState {
  return {
    conditionTag: estimate.condition_tag,
    preExisting: false,
    accident: false,
    inceptionDate: estimate.inception_date,
    admissionDate: estimate.admission_date,
    continuityCreditMonths: 0,
  };
}

/**
 * Whole months and days between two dates — display-only mirror of the
 * server derivation so the user can see the cover elapsed implied by
 * the dates they typed. The server result governs the calculation.
 */
export function elapsedFromDates(
  inception: string | null,
  admission: string | null,
  creditMonths: number,
): { months: number; days: number } | null {
  if (!inception || !admission) return null;
  const start = new Date(inception + "T00:00:00");
  const end = new Date(admission + "T00:00:00");
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return null;
  let months =
    (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
  if (end.getDate() < start.getDate()) months -= 1;
  const days = Math.round((end.getTime() - start.getTime()) / 86_400_000);
  return { months: months + creditMonths, days: days + creditMonths * 30 };
}

/** The demo baseline: scenario B (continuity confirmed, room above cap). */
export function baselineScenario(estimate: Estimate): ScenarioState {
  return {
    roomAtCap: false,
    continuityConfirmed: true,
    grossBill: estimate.gross_bill,
  };
}

export type ScenarioField = "room_rate_per_night" | "policy_month_at_admit" | "gross_bill";

function safeNum(s: string): number {
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

export function changedFields(base: ScenarioState, next: ScenarioState): ScenarioField[] {
  const fields: ScenarioField[] = [];
  if (base.roomAtCap !== next.roomAtCap) fields.push("room_rate_per_night");
  if (base.continuityConfirmed !== next.continuityConfirmed) fields.push("policy_month_at_admit");
  if (safeNum(base.grossBill) !== safeNum(next.grossBill)) fields.push("gross_bill");
  return fields;
}

/** Effective policy month: continuity credit means the wait counts as served. */
export function effectiveMonth(estimate: Estimate, continuityConfirmed: boolean): number {
  if (!continuityConfirmed) return estimate.policy_month_at_admit;
  const required = estimate.waiting_months_required ?? estimate.policy_month_at_admit;
  return Math.max(estimate.policy_month_at_admit, required);
}

export function roomRateFor(estimate: Estimate, atCap: boolean): string {
  if (atCap && estimate.room_cap_per_day !== null) return estimate.room_cap_per_day;
  return estimate.room_rate_per_night;
}

/**
 * Charge lines for a room rate. Choosing a cheaper room does not change the
 * hospital's total estimate in this model (package pricing): the room
 * difference moves to surgeon fees, so lines still sum to the gross bill.
 * This mirrors the server-side plan derivation exactly.
 */
function chargesForRoomRate(estimate: Estimate, rate: string): ChargeItemInput[] {
  const newRoom = dec(rate) * estimate.nights;
  const roomCharge = estimate.charges.find((c) => c.nights !== null);
  const delta = roomCharge ? dec(roomCharge.amount) - newRoom : 0;
  let surgeonBumped = false;
  return estimate.charges.map((c) => {
    if (c.nights !== null) {
      return { ...c, amount: String(newRoom) };
    }
    if (!surgeonBumped && c.name.toLowerCase().includes("surgeon")) {
      surgeonBumped = true;
      return { ...c, amount: String(dec(c.amount) + delta) };
    }
    return c;
  });
}

/** The apportionment interpretation currently in force for this session. */
export function apportionmentFor(clauses: Clause[]): string {
  const clause = clauses.find((c) => c.rule.type === "apportionment_base");
  if (!clause) return "unresolved";
  if (clause.verification.interpretation_status === "unknown") return "unresolved";
  const scope = clause.rule.params["scope"] ?? "unresolved";
  return scope;
}

export function buildSimulateRequest(
  estimate: Estimate,
  clauses: Clause[],
  scenario: ScenarioState,
  claim: ClaimState,
): SimulateRequest {
  const rate = roomRateFor(estimate, scenario.roomAtCap);
  // When dates are supplied the server derives elapsed months/days from
  // them (plus any credited months); the continuity toggle remains the
  // what-if lever "treat the waiting period as served". The explicit
  // month below still anchors the counterfactual change payloads.
  const derived = elapsedFromDates(claim.inceptionDate, claim.admissionDate, 0);
  return {
    gross: scenario.grossBill,
    charges: chargesForRoomRate(estimate, rate),
    room_rate_per_night: rate,
    nights: estimate.nights,
    assumptions: {
      policy_month_at_admit:
        derived !== null
          ? derived.months + claim.continuityCreditMonths
          : effectiveMonth(estimate, scenario.continuityConfirmed),
      remaining_sum_insured: estimate.sum_insured,
      sum_insured: estimate.sum_insured,
      non_payable_total: estimate.non_payable_total,
      apportionment_base: apportionmentFor(clauses),
      continuity_confirmed: scenario.continuityConfirmed,
      condition_tag: claim.conditionTag,
      is_pre_existing: claim.preExisting,
      is_accident: claim.accident,
      inception_date: claim.inceptionDate,
      admission_date: claim.admissionDate,
      continuity_credit_months: claim.continuityCreditMonths,
    },
  };
}

/** The single-variable change payload for /counterfactual, baseline → scenario. */
export function counterfactualChange(
  estimate: Estimate,
  base: ScenarioState,
  next: ScenarioState,
  field: ScenarioField,
): { field: string; from_val: string | number; to_val: string | number } {
  switch (field) {
    case "room_rate_per_night":
      return {
        field,
        from_val: roomRateFor(estimate, base.roomAtCap),
        to_val: roomRateFor(estimate, next.roomAtCap),
      };
    case "policy_month_at_admit":
      return {
        field,
        from_val: effectiveMonth(estimate, base.continuityConfirmed),
        to_val: effectiveMonth(estimate, next.continuityConfirmed),
      };
    case "gross_bill":
      return { field, from_val: base.grossBill, to_val: next.grossBill };
  }
}

const RULE_ID_TO_CLAUSE_TYPE: Record<string, string> = {
  waiting_period: "waiting_period",
  non_payable: "non_payable",
  room_rent_limit: "room_rent_limit",
  proportionate_deduction: "apportionment_base",
  co_payment: "co_payment",
  deductible: "deductible",
  exclusion: "exclusion",
};

/** Evidence status behind a deduction row — by exact source clause when known. */
export function statusForDeduction(
  clauses: Clause[],
  deduction: { rule_id: string; source_clause_id: string | null },
): ClauseStatus {
  if (deduction.source_clause_id) {
    const clause = clauses.find((c) => c.clause_id === deduction.source_clause_id);
    if (clause) return clause.verification.interpretation_status;
  }
  return statusForRule(clauses, deduction.rule_id);
}

/** Evidence status behind a deduction row, via its rule → clause mapping. */
export function statusForRule(clauses: Clause[], ruleId: string): ClauseStatus {
  const clauseType = RULE_ID_TO_CLAUSE_TYPE[ruleId] ?? ruleId;
  const clause =
    clauses.find((c) => c.rule.type === clauseType) ??
    clauses.find((c) => c.rule.type === "proportionate_deduction" && ruleId === "proportionate_deduction");
  return clause ? clause.verification.interpretation_status : "unknown";
}

const STATUS_PRECEDENCE: ClauseStatus[] = [
  "conflicting",
  "unknown",
  "unverified",
  "user_confirmed",
  "verified",
  "synthetic",
];

/**
 * The weakest evidence status among the material clauses — the honest label
 * for computed totals, whose trust is bounded by their inputs.
 */
export function weakestMaterialStatus(clauses: Clause[], hasUnresolved: boolean): ClauseStatus {
  if (hasUnresolved) return "unknown";
  const material = clauses.filter((c) =>
    ["room_rent_limit", "waiting_period", "non_payable", "apportionment_base"].includes(c.rule.type),
  );
  let weakest: ClauseStatus = "synthetic";
  let weakestRank = STATUS_PRECEDENCE.length - 1;
  for (const c of material) {
    const s = c.verification.interpretation_status;
    const rank = STATUS_PRECEDENCE.indexOf(s);
    if (rank >= 0 && rank < weakestRank) {
      weakestRank = rank;
      weakest = s;
    }
  }
  return weakest;
}
