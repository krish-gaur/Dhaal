"use client";

import type { LoanMetrics } from "@/lib/api";
import { dec, formatPct } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import { Money } from "./Money";

/**
 * Synthetic loan offers as a plain table. APR is the server's IRR figure,
 * shown nominal and effective, never labelled "interest rate" (F-L4).
 */
export function LoanTable({ loans, lang }: { loans: LoanMetrics[]; lang: Lang }) {
  return (
    <div>
      <p className="muted small">{t("s3_loans_synthetic", lang)}</p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">{t("s3_col_offer", lang)}</th>
              <th scope="col" className="money-cell">
                {t("s3_col_emi", lang)}
              </th>
              <th scope="col" className="money-cell">
                {t("s3_col_apr_nominal", lang)}
              </th>
              <th scope="col" className="money-cell">
                {t("s3_col_apr_effective", lang)}
              </th>
              <th scope="col" className="money-cell">
                {t("s3_col_total_out", lang)}
              </th>
              <th scope="col" className="money-cell">
                {t("s3_col_lean", lang)}
              </th>
            </tr>
          </thead>
          <tbody>
            {loans.map((loan) => (
              <tr key={loan.label}>
                <td>
                  {loan.label}
                  <span className="muted small"> · </span>
                  <Money
                    amount={{ value: loan.principal, status: "synthetic" }}
                    lang={lang}
                    showStatus={false}
                  />
                </td>
                <td className="money-cell">
                  <Money amount={{ value: loan.emi, status: "synthetic" }} lang={lang} dp={2} showStatus={false} />
                </td>
                <td className="money-cell">{formatPct(dec(loan.apr_nominal))}</td>
                <td className="money-cell">{formatPct(dec(loan.apr_effective))}</td>
                <td className="money-cell">
                  <Money
                    amount={{ value: loan.total_cash_out, status: "synthetic" }}
                    lang={lang}
                    dp={2}
                    showStatus={false}
                  />
                </td>
                <td className="money-cell" data-testid={`lean-${loan.label}`}>
                  <Money
                    amount={{ value: loan.free_cash_lean_month, status: "synthetic" }}
                    lang={lang}
                    dp={2}
                    showStatus={false}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
