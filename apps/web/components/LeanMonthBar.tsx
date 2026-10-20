"use client";

import type { LoanMetrics } from "@/lib/api";
import { dec, formatINRDense } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

/**
 * Free cash in the worst income month, one marker per offer, on a
 * −₹6,000…+₹10,000 scale. Hand-built divs — no chart library.
 * The blunt caption is shown only when it is literally true (every
 * offer negative); it is never softened or shown when false.
 */
const MIN = -6000;
const MAX = 10000;

function pct(value: number): number {
  const clamped = Math.min(MAX, Math.max(MIN, value));
  return ((clamped - MIN) / (MAX - MIN)) * 100;
}

export function LeanMonthBar({ loans, lang }: { loans: LoanMetrics[]; lang: Lang }) {
  const allNegative = loans.length > 0 && loans.every((l) => dec(l.free_cash_lean_month) < 0);
  return (
    <div>
      <p className="small muted" style={{ marginBottom: 20 }}>
        {t("s3_lean_bar_label", lang)}
      </p>
      <div className="lean-bar" role="img" aria-label={t("s3_lean_bar_label", lang)}>
        <span className="zero-line" style={{ left: `${pct(0)}%` }} />
        <span className="axis-label" style={{ left: 0 }}>
          {formatINRDense(MIN)}
        </span>
        <span className="axis-label" style={{ left: `calc(${pct(0)}% - 4px)` }}>
          0
        </span>
        <span className="axis-label" style={{ right: 0 }}>
          +{formatINRDense(MAX)}
        </span>
        {loans.map((loan) => (
          <span
            key={loan.label}
            className="marker"
            style={{ left: `${pct(dec(loan.free_cash_lean_month))}%` }}
            title={`${loan.label}: ${loan.free_cash_lean_month}`}
          >
            <span>{loan.label}</span>
          </span>
        ))}
      </div>
      {allNegative ? (
        <p style={{ marginTop: 28 }} data-testid="lean-caption">
          {t("s3_lean_caption", lang)}
        </p>
      ) : null}
    </div>
  );
}
