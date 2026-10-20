"use client";

import { useState } from "react";
import type { Clause } from "@/lib/api";
import { ruleLabel, t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import { StatusDot } from "./StatusDot";

export type ClauseAction =
  | { kind: "confirm" }
  | { kind: "unknown" }
  | { kind: "correct"; params: Record<string, string> };

/**
 * One extracted clause: collapsed summary, expandable quote + verification
 * detail, and the three user decisions. quote_found and interpretation
 * status are shown as separate facts — never one "verified" tick (F-E3).
 */
export function ClauseRow({
  clause,
  lang,
  isMaterial,
  busy,
  expanded,
  onToggle,
  onView,
  onAction,
}: {
  clause: Clause;
  lang: Lang;
  isMaterial: boolean;
  busy: boolean;
  expanded: boolean;
  onToggle: () => void;
  onView: () => void;
  onAction: (action: ClauseAction) => void;
}) {
  const v = clause.verification;
  const [correcting, setCorrecting] = useState(false);
  const [params, setParams] = useState<Record<string, string>>(clause.rule.params);

  const valueSummary = summaryFor(clause);
  const decided =
    v.interpretation_status === "verified" ||
    v.interpretation_status === "user_confirmed" ||
    v.interpretation_status === "unknown";

  return (
    <div className="clause-row" id={clause.clause_id}>
      <button
        type="button"
        className="row-head"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        <span style={{ fontWeight: 500 }}>{ruleLabel(clause.rule.type, lang)}</span>
        <span className="muted small">{valueSummary}</span>
        {clause.page !== null ? (
          <span className="muted small">{t("page_of", lang, { page: clause.page })}</span>
        ) : null}
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 10, alignItems: "center" }}>
          {isMaterial && !decided ? (
            <span className="required-marker">{t("s2_required", lang)}</span>
          ) : null}
          <StatusDot status={v.interpretation_status} lang={lang} />
        </span>
      </button>

      {expanded ? (
        <div className="row-body">
          <p className="small muted" style={{ marginBottom: 4 }}>
            {t("s2_quote_label", lang)}
          </p>
          <blockquote>{clause.quote ?? "—"}</blockquote>

          <p className="small muted" style={{ marginBottom: 4 }}>
            {t("s2_rule_label", lang)}
          </p>
          <p className="small" style={{ marginBottom: 12 }}>
            {Object.entries(clause.rule.params)
              .map(([k, val]) => `${k} = ${val}`)
              .join(" · ") || "—"}
          </p>

          <ul className="small" style={{ margin: "0 0 12px", paddingLeft: 18 }}>
            <li>{v.quote_found ? t("s2_quote_found", lang) : t("s2_quote_missing", lang)}</li>
            <li>{v.numbers_supported ? t("s2_numbers_ok", lang) : t("s2_numbers_bad", lang)}</li>
            <li>{t("s2_schema_ok", lang)}: {v.schema_valid ? "✓" : "✗"}</li>
          </ul>

          {v.reason ? (
            <p className="small" style={{ marginBottom: 12 }}>
              <span className="muted">{t("s2_reason_label", lang)}: </span>
              {v.reason}
            </p>
          ) : null}

          {correcting ? (
            <CorrectForm
              clause={clause}
              lang={lang}
              params={params}
              setParams={setParams}
              busy={busy}
              onCancel={() => setCorrecting(false)}
              onSave={() => {
                setCorrecting(false);
                onAction({ kind: "correct", params });
              }}
            />
          ) : (
            <div className="clause-actions">
              <button
                type="button"
                className="btn btn-small"
                disabled={busy}
                onClick={() => onAction({ kind: "confirm" })}
              >
                {t("s2_confirm", lang)}
              </button>
              <button
                type="button"
                className="btn btn-small"
                disabled={busy}
                onClick={() => {
                  setParams(clause.rule.params);
                  setCorrecting(true);
                }}
              >
                {t("s2_correct", lang)}
              </button>
              <button
                type="button"
                className="btn btn-small"
                disabled={busy}
                onClick={() => onAction({ kind: "unknown" })}
              >
                {t("s2_mark_unknown", lang)}
              </button>
              <button type="button" className="btn btn-small" onClick={onView}>
                {t("s2_view_doc", lang)}
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function CorrectForm({
  clause,
  lang,
  params,
  setParams,
  busy,
  onCancel,
  onSave,
}: {
  clause: Clause;
  lang: Lang;
  params: Record<string, string>;
  setParams: (p: Record<string, string>) => void;
  busy: boolean;
  onCancel: () => void;
  onSave: () => void;
}) {
  if (clause.rule.type === "apportionment_base") {
    const options: Array<{ value: string; label: string }> = [
      { value: "surgeon_ot_diagnostics", label: t("s2_app_surgeon", lang) },
      { value: "all_medical_expenses", label: t("s2_app_all", lang) },
      { value: "room_related_only", label: t("s2_app_room", lang) },
    ];
    return (
      <fieldset style={{ border: "1px solid var(--color-border)", borderRadius: 6 }}>
        <legend className="small" style={{ padding: "0 6px" }}>
          {t("s2_apportionment_prompt", lang)}
        </legend>
        {options.map((o) => (
          <label
            key={o.value}
            className={`radio-card${params["scope"] === o.value ? " selected" : ""}`}
          >
            <input
              type="radio"
              name={`scope-${clause.clause_id}`}
              value={o.value}
              checked={params["scope"] === o.value}
              onChange={() => setParams({ ...params, scope: o.value })}
            />
            <span>{o.label}</span>
            {params["scope"] === o.value ? <span className="tick">✓</span> : null}
          </label>
        ))}
        <div className="clause-actions">
          <button type="button" className="btn btn-small btn-primary" disabled={busy} onClick={onSave}>
            {t("s2_save", lang)}
          </button>
          <button type="button" className="btn btn-small" disabled={busy} onClick={onCancel}>
            {t("s2_cancel", lang)}
          </button>
        </div>
      </fieldset>
    );
  }

  const fields: Array<{ key: string; label: string }> =
    clause.rule.type === "room_rent_limit"
      ? [{ key: "value", label: t("s2_room_value_label", lang) }]
      : clause.rule.type === "waiting_period"
        ? [{ key: "months_required", label: t("s2_waiting_months_label", lang) }]
        : Object.keys(params).map((k) => ({ key: k, label: k }));

  return (
    <div>
      {fields.map((f) => (
        <div key={f.key} style={{ marginBottom: 10 }}>
          <label className="small" htmlFor={`${clause.clause_id}-${f.key}`} style={{ display: "block", marginBottom: 4 }}>
            {f.label}
          </label>
          <input
            id={`${clause.clause_id}-${f.key}`}
            type="text"
            inputMode="decimal"
            value={params[f.key] ?? ""}
            onChange={(e) => setParams({ ...params, [f.key]: e.target.value })}
            style={{ width: "100%", maxWidth: 320 }}
          />
        </div>
      ))}
      <div className="clause-actions">
        <button type="button" className="btn btn-small btn-primary" disabled={busy} onClick={onSave}>
          {t("s2_save", lang)}
        </button>
        <button type="button" className="btn btn-small" disabled={busy} onClick={onCancel}>
          {t("s2_cancel", lang)}
        </button>
      </div>
    </div>
  );
}

function summaryFor(clause: Clause): string {
  const p = clause.rule.params;
  switch (clause.rule.type) {
    case "room_rent_limit":
      return p["basis"] === "pct_sum_insured_per_day"
        ? `${p["value"] ?? ""} × SI/day`
        : `₹${p["value"] ?? ""}/day`;
    case "waiting_period":
      return `${p["months_required"] ?? ""} months`;
    case "non_payable":
      return (p["items"] ?? "").split(",").filter(Boolean).length + " items";
    case "apportionment_base":
      return p["scope"] ?? "";
    case "co_payment":
      return `${p["pct"] ?? ""}`;
    case "deductible":
      return `₹${p["amount"] ?? ""}`;
    default:
      return "";
  }
}
