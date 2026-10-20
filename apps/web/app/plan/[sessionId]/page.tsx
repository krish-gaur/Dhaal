"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { FixtureBanner } from "@/components/AppHeader";
import { Money } from "@/components/Money";
import { ErrorBox, Loading } from "@/components/States";
import { getPlan, getSession } from "@/lib/api";
import type { Plan } from "@/lib/api";
import { t } from "@/lib/i18n";
import { useLang } from "@/lib/useLang";
import { withStatus } from "@/lib/types";

/** Screen 4 — What to do: server-ranked steps, editable draft, unresolved evidence. */
export default function PlanPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const { lang } = useLang();

  const [plan, setPlan] = useState<Plan | null>(null);
  const [mode, setMode] = useState<"fixture" | "live">("live");
  const [draft, setDraft] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([getPlan(sessionId), getSession(sessionId)]);
      setPlan(p);
      setMode(s.mode);
      setDraft(p.draft_message);
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error !== null && plan === null) {
    return (
      <div className="page page-narr">
        <h1>{t("s4_title", lang)}</h1>
        <ErrorBox error={error} lang={lang} onRetry={() => void load()} />
      </div>
    );
  }
  if (plan === null) {
    return (
      <div className="page">
        <Loading lang={lang} />
      </div>
    );
  }

  const qs = lang === "hi" ? "?lang=hi" : "";

  return (
    <>
      {mode === "fixture" ? <FixtureBanner /> : null}
      <div className="page" style={{ maxWidth: 860 }}>
        <h1>{t("s4_title", lang)}</h1>
        <p className="muted">{t("s4_intro", lang)}</p>

        <div>
          {plan.steps.map((step) => (
            <div className="step-row" key={step.rank}>
              <span className="step-rank">{step.rank}</span>
              <div>
                <p style={{ fontWeight: 500, marginBottom: 4 }}>{step.title}</p>
                <p style={{ marginBottom: 4 }}>{step.why}</p>
                <p className="muted small" style={{ marginBottom: 4 }}>
                  {step.effort}
                </p>
                {step.rupee_value !== "0" ? (
                  <p className="small" style={{ marginBottom: 0 }}>
                    {t("s4_worth", lang, { amount: "" })}{" "}
                    <Money
                      amount={withStatus(step.rupee_value, mode === "fixture" ? "synthetic" : "unverified")}
                      lang={lang}
                    />
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        <h2>{t("s4_draft_title", lang)}</h2>
        <label className="field-label" htmlFor="draft-message">
          {t("s4_draft_label", lang)}
        </label>
        <textarea
          id="draft-message"
          className="full"
          rows={16}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn-small"
            onClick={() => {
              void navigator.clipboard.writeText(draft).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              });
            }}
          >
            {copied ? t("s4_copied", lang) : t("s4_copy", lang)}
          </button>
        </div>

        <h2>{t("s4_unresolved_title", lang)}</h2>
        {plan.unresolved_items.length > 0 ? (
          <ul>
            {plan.unresolved_items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">{t("s4_none_unresolved", lang)}</p>
        )}

        <div className="nav-row">
          <Link href={`/simulate/${sessionId}${qs}`} className="btn">
            {t("s4_back_sim", lang)}
          </Link>
          <Link href={`/audit/${sessionId}${qs}`} className="btn btn-primary">
            {t("s4_to_audit", lang)}
          </Link>
        </div>

        <p className="footer-disclaimer">{t("s4_disclaimer", lang)}</p>
      </div>
    </>
  );
}
