"use client";

import { useState } from "react";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

/** One-line consent summary, expandable to a four-row table. Collapsed by default. */
export function ConsentBlock({ lang }: { lang: Lang }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="consent">
      <button
        type="button"
        className="consent-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {t("consent_title", lang)} <span aria-hidden="true">{open ? "▾" : "▸"}</span>
      </button>
      {open ? (
        <table>
          <tbody>
            <tr>
              <th scope="row">{t("consent_purpose_h", lang)}</th>
              <td>{t("consent_purpose", lang)}</td>
            </tr>
            <tr>
              <th scope="row">{t("consent_docs_h", lang)}</th>
              <td>{t("consent_docs", lang)}</td>
            </tr>
            <tr>
              <th scope="row">{t("consent_retention_h", lang)}</th>
              <td>{t("consent_retention", lang)}</td>
            </tr>
            <tr>
              <th scope="row">{t("consent_dont_h", lang)}</th>
              <td>{t("consent_dont", lang)}</td>
            </tr>
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
