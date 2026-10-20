"use client";

import { useState } from "react";
import type { ClaimResult, ClauseStatus } from "@/lib/api";
import { dec, formatINR } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import type { WithStatus } from "@/lib/types";
import { Money } from "./Money";

/**
 * The calculation waterfall as a plain <table>: gross bill, each deduction
 * with its basis one click away, then insurer / you. The final row carries
 * a runtime conservation check (insurer + you == gross) — displayed, not
 * assumed.
 */
export function WaterfallTable({
  result,
  previous,
  lang,
  grossStatus,
  totalStatus,
  statusForRule,
}: {
  result: ClaimResult;
  previous: ClaimResult | null;
  lang: Lang;
  grossStatus: ClauseStatus;
  totalStatus: ClauseStatus;
  statusForRule: (ruleId: string) => ClauseStatus;
}) {
  const [openBasis, setOpenBasis] = useState<string | null>(null);

  const prevByRule = new Map<string, string>();
  if (previous) {
    for (const d of previous.deductions) prevByRule.set(d.rule_id, d.amount);
  }
  const changed = (ruleId: string, amount: string): boolean =>
    previous !== null && prevByRule.get(ruleId) !== amount;

  const conservationOk =
    dec(result.insurer_payment) + dec(result.out_of_pocket) === dec(result.gross_bill);

  const ws = (value: string, status: ClauseStatus): WithStatus<string> => ({ value, status });

  return (
    <div className="table-scroll">
      <table className="waterfall">
        <thead>
          <tr>
            <th scope="col">{t("s3_waterfall_title", lang)}</th>
            <th scope="col" className="amount">
              ₹
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{t("s3_gross", lang)}</td>
            <td className="amount">
              <Money amount={ws(result.gross_bill, grossStatus)} lang={lang} showStatus={false} />
            </td>
          </tr>
          {result.deductions.map((d) => {
            const key = `${d.rule_id}-${d.name}`;
            const open = openBasis === key;
            return (
              <tr key={key} className={changed(d.rule_id, d.amount) ? "row-flash" : undefined}>
                <td>
                  <span>{d.name}</span>
                  <span className="muted small"> · {d.citation}</span>
                  <button
                    type="button"
                    className="basis-btn"
                    aria-label={open ? t("s3_hide_calc", lang) : t("s3_show_calc", lang)}
                    aria-expanded={open}
                    onClick={() => setOpenBasis(open ? null : key)}
                  >
                    ?
                  </button>
                  {open ? (
                    <div className="basis-text" style={{ marginTop: 6 }}>
                      {d.basis}
                    </div>
                  ) : null}
                </td>
                <td className="amount">
                  <Money
                    amount={ws(String(-dec(d.amount)), statusForRule(d.rule_id))}
                    lang={lang}
                  />
                </td>
              </tr>
            );
          })}
          <tr>
            <td>{t("s3_insurer_pays", lang)}</td>
            <td className="amount">
              <Money
                amount={ws(result.insurer_payment, totalStatus)}
                lang={lang}
                showStatus={false}
                testId="insurer-payment"
              />
            </td>
          </tr>
          <tr className="total-row">
            <td>{t("you_pay", lang)}</td>
            <td className="amount">
              <Money
                amount={ws(result.out_of_pocket, totalStatus)}
                lang={lang}
                showStatus={false}
                testId="oop-total"
              />
            </td>
          </tr>
        </tbody>
      </table>
      {conservationOk ? (
        <p className="muted small" style={{ marginTop: 8 }} data-testid="conservation-check">
          {t("s3_check_line", lang)}: {formatINR(dec(result.insurer_payment))} +{" "}
          {formatINR(dec(result.out_of_pocket))} = {formatINR(dec(result.gross_bill))} ✓
        </p>
      ) : null}
    </div>
  );
}
