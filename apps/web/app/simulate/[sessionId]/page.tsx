"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FixtureBanner } from "@/components/AppHeader";
import { DeltaChip } from "@/components/DeltaChip";
import { LeanMonthBar } from "@/components/LeanMonthBar";
import { LoanTable } from "@/components/LoanTable";
import { ErrorBox, Loading } from "@/components/States";
import { StatusDot } from "@/components/StatusDot";
import { TogglePanel } from "@/components/TogglePanel";
import { VerdictBar } from "@/components/VerdictBar";
import { WaterfallTable } from "@/components/WaterfallTable";
import { counterfactual, getClauses, getEstimate, getLoans, getSession, simulate } from "@/lib/api";
import type { ClaimResult, Clause, CounterfactualResult, Estimate, LoanMetrics, SessionDetail } from "@/lib/api";
import { dec, formatINR } from "@/lib/format";
import { t } from "@/lib/i18n";
import {
  baselineScenario,
  buildSimulateRequest,
  changedFields,
  counterfactualChange,
  effectiveMonth,
  statusForRule,
  weakestMaterialStatus,
} from "@/lib/scenario";
import type { ScenarioField, ScenarioState } from "@/lib/scenario";
import { useLang } from "@/lib/useLang";
import { withStatus } from "@/lib/types";

/** Screen 3 — What you'll pay: estimate, waterfall, one-change scenarios, funding gap. */
export default function SimulatePage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const { lang } = useLang();
  const router = useRouter();

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [loans, setLoans] = useState<LoanMetrics[] | null>(null);
  const [scenario, setScenario] = useState<ScenarioState | null>(null);
  const [result, setResult] = useState<ClaimResult | null>(null);
  const [previous, setPrevious] = useState<ClaimResult | null>(null);
  const [cf, setCf] = useState<{ field: ScenarioField; data: CounterfactualResult } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const runSeq = useRef(0);
  const lastResultRef = useRef<ClaimResult | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c, e, l] = await Promise.all([
        getSession(sessionId),
        getClauses(sessionId),
        getEstimate(sessionId),
        getLoans(sessionId),
      ]);
      setSession(s);
      setClauses(c);
      setEstimate(e);
      setLoans(l);
      setScenario((prev) => prev ?? baselineScenario(e));
      setError(null);
    } catch (err) {
      setError(err);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const baseline = useMemo(() => (estimate ? baselineScenario(estimate) : null), [estimate]);

  // Re-simulate on every scenario change (small debounce for the bill input).
  useEffect(() => {
    if (!estimate || !clauses || !scenario || !baseline) return;
    const grossNum = Number(scenario.grossBill);
    if (!Number.isFinite(grossNum) || grossNum < 0) return;
    const seq = ++runSeq.current;
    const timer = setTimeout(() => {
      const body = buildSimulateRequest(estimate, clauses, scenario);
      simulate(sessionId, body)
        .then((r) => {
          if (runSeq.current !== seq) return;
          setPrevious(lastResultRef.current);
          lastResultRef.current = r;
          setResult(r);
        })
        .catch((e: unknown) => {
          if (runSeq.current === seq) setError(e);
        });

      const fields = changedFields(baseline, scenario);
      if (fields.length === 1 && fields[0]) {
        const field = fields[0];
        const baseBody = buildSimulateRequest(estimate, clauses, baseline);
        counterfactual(sessionId, baseBody, counterfactualChange(estimate, baseline, scenario, field))
          .then((data) => {
            if (runSeq.current === seq) setCf({ field, data });
          })
          .catch(() => {
            if (runSeq.current === seq) setCf(null);
          });
      } else {
        setCf(null);
      }
    }, 200);
    return () => clearTimeout(timer);
    // result intentionally excluded: previous-result flash reads the ref-ish state once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimate, clauses, scenario, baseline, sessionId]);

  if (error !== null && result === null) {
    return (
      <div className="page page-narr">
        <h1>{t("s3_title", lang)}</h1>
        <ErrorBox error={error} lang={lang} onRetry={() => void load()} />
        <p>
          <Link href={`/evidence/${sessionId}`}>← {t("s2_title", lang)}</Link>
        </p>
      </div>
    );
  }
  if (!session || !clauses || !estimate || !scenario || !baseline) {
    return (
      <div className="page">
        <Loading lang={lang} />
      </div>
    );
  }

  const fields = changedFields(baseline, scenario);
  const hasUnresolved = (result?.unresolved.length ?? 0) > 0;
  const totalStatus = weakestMaterialStatus(clauses, hasUnresolved);
  const grossStatus = estimate.synthetic ? "synthetic" : "user_confirmed";
  const savings = dec(estimate.affordability.savings);
  const oop = result ? dec(result.out_of_pocket) : 0;
  const gap = Math.max(0, oop - savings);
  const principal = loans && loans[0] ? loans[0].principal : "0";
  const meanIncome = dec(estimate.affordability.mean_income);
  const monthsOfIncome = meanIncome > 0 ? (oop / meanIncome).toFixed(1) : "0";

  const deltaText = (field: ScenarioField): string => {
    if (field === "room_rate_per_night") {
      const page = clauses.find((c) => c.rule.type === "room_rent_limit")?.page ?? 4;
      return t("s3_delta_room", lang, { page });
    }
    if (field === "policy_month_at_admit") {
      const page = clauses.find((c) => c.rule.type === "waiting_period")?.page ?? 5;
      return t("s3_delta_continuity", lang, { page });
    }
    return t("s3_delta_bill", lang);
  };

  const clauseIdForField = (field: ScenarioField): string | null => {
    if (field === "room_rate_per_night")
      return clauses.find((c) => c.rule.type === "room_rent_limit")?.clause_id ?? null;
    if (field === "policy_month_at_admit")
      return clauses.find((c) => c.rule.type === "waiting_period")?.clause_id ?? null;
    return null;
  };

  return (
    <>
      {session.mode === "fixture" ? <FixtureBanner /> : null}
      <div className="page" style={{ paddingBottom: 40 }}>
        <h1>{t("s3_title", lang)}</h1>

        {error !== null ? <ErrorBox error={error} lang={lang} onRetry={() => void load()} /> : null}

        {result ? (
          <>
            <p className="muted" style={{ marginBottom: 4 }}>
              {t("s3_your_oop", lang)}
            </p>
            {hasUnresolved && result.range_low !== null && result.range_high !== null ? (
              <>
                <p className="oop-figure">
                  <span data-testid="oop">
                    {formatINR(dec(result.range_low))} – {formatINR(dec(result.range_high))}
                  </span>{" "}
                  <StatusDot status={totalStatus} lang={lang} />
                </p>
                <p className="muted">
                  {t("s3_range_caption", lang)} {t("s3_range_point", lang)}:{" "}
                  {formatINR(dec(result.out_of_pocket))}
                </p>
              </>
            ) : (
              <p className="oop-figure" data-testid="oop">
                {formatINR(oop)}
              </p>
            )}
            <p className="muted">
              {t("s3_oop_caption", lang)} ≈ {monthsOfIncome} × {formatINR(meanIncome)}
            </p>

            <h2>{t("s3_waterfall_title", lang)}</h2>
            <WaterfallTable
              result={result}
              previous={previous}
              lang={lang}
              grossStatus={grossStatus}
              totalStatus={totalStatus}
              statusForRule={(ruleId) => statusForRule(clauses, ruleId)}
            />

            {hasUnresolved ? (
              <>
                <h2>{t("s3_unresolved_title", lang)}</h2>
                <ul>
                  {result.unresolved.map((u) => (
                    <li key={u.rule_type + u.reason}>{u.reason}</li>
                  ))}
                </ul>
              </>
            ) : null}

            <h2>{t("s3_scenario_title", lang)}</h2>
            <TogglePanel
              estimate={estimate}
              scenario={scenario}
              changedCount={fields.length}
              lang={lang}
              onChange={setScenario}
            />
            {cf !== null && fields.length === 1 ? (
              <DeltaChip
                oopDelta={cf.data.oop_delta}
                text={deltaText(cf.field)}
                onClick={() => {
                  const cid = clauseIdForField(cf.field);
                  router.push(`/evidence/${sessionId}${cid ? `#${cid}` : ""}`);
                }}
              />
            ) : null}

            <h2>{t("s3_savings_title", lang)}</h2>
            <p>
              {t("s3_savings_line", lang, { savings: formatINR(savings) })}{" "}
              {t("s3_gap_line", lang, { gap: formatINR(gap) })}
            </p>
            <p className="muted">
              {t("s3_worst_case", lang, {
                gross: formatINR(dec(result.gross_bill)),
                principal: formatINR(dec(principal)),
              })}
            </p>

            {loans ? (
              <>
                <h2>{t("s3_loans_title", lang)}</h2>
                <LoanTable loans={loans} lang={lang} />
                <LeanMonthBar loans={loans} lang={lang} />
              </>
            ) : null}

            <h2>{t("s3_assumptions_title", lang)}</h2>
            <ul className="small">
              <li>
                {t("s3_assump_month", lang, {
                  month: effectiveMonth(estimate, scenario.continuityConfirmed),
                })}
              </li>
              <li>
                {t("s3_assump_si", lang, { si: formatINR(dec(estimate.sum_insured)) })}
              </li>
              <li>
                {t("s3_assump_nonpayable", lang, {
                  amount: formatINR(dec(estimate.non_payable_total)),
                })}
              </li>
              <li>{apportionmentLabel(clauses, lang)}</li>
            </ul>
          </>
        ) : (
          <Loading lang={lang} />
        )}
      </div>

      {result ? (
        <VerdictBar
          oop={withStatus(result.out_of_pocket, totalStatus)}
          lang={lang}
          action={
            <Link href={`/plan/${sessionId}${lang === "hi" ? "?lang=hi" : ""}`} className="btn btn-primary">
              {t("s3_to_plan", lang)}
            </Link>
          }
        />
      ) : null}
    </>
  );
}

function apportionmentLabel(clauses: Clause[], lang: "en" | "hi"): string {
  const clause = clauses.find((c) => c.rule.type === "apportionment_base");
  const scope = clause?.rule.params["scope"] ?? "unresolved";
  const key =
    scope === "surgeon_ot_diagnostics"
      ? "base_surgeon_ot_diagnostics"
      : scope === "all_medical_expenses"
        ? "base_all_medical_expenses"
        : scope === "room_related_only"
          ? "base_room_related_only"
          : "base_unresolved";
  return t("s3_assump_base", lang, { base: t(key, lang) });
}
