"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FixtureBanner } from "@/components/AppHeader";
import { ConsentBlock } from "@/components/ConsentBlock";
import { PolicySearch } from "@/components/PolicySearch";
import type { PolicySelection } from "@/components/PolicySearch";
import { ErrorBox } from "@/components/States";
import { createSession, loadFixtureDocument, uploadDocument } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { StringKey } from "@/lib/i18n";
import { useLang } from "@/lib/useLang";

const GOALS: Array<{ id: string; labelKey: StringKey }> = [
  { id: "hospital_procedure", labelKey: "s1_goal_procedure" },
  { id: "planned_admission", labelKey: "s1_goal_admission" },
  { id: "checking_policy", labelKey: "s1_goal_checking" },
];

type IdentifyMode = "find" | "upload" | "sample";

/**
 * Screen 1 — Goal + policy identification. Policy-first: nothing is
 * simulated until the exact policy (and version) is identified from the
 * catalogue of held wordings, or the user uploads their own policy PDF.
 * A clearly-labelled fictional sample remains for trying Dhaal out.
 */
export default function GoalPage() {
  const { lang } = useLang();
  const router = useRouter();
  const [goal, setGoal] = useState<string>(GOALS[0]?.id ?? "hospital_procedure");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<IdentifyMode>("sample");
  const [selection, setSelection] = useState<PolicySelection | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [declaredInsurer, setDeclaredInsurer] = useState("");
  const [declaredProduct, setDeclaredProduct] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const canStart =
    mode === "sample" ||
    (mode === "find" && selection !== null && selection.version !== null) ||
    (mode === "upload" && file !== null);

  async function start() {
    setError(null);
    if (mode === "upload" && file === null) {
      setError(new Error(t("s1_file_required", lang)));
      return;
    }
    if (mode === "find" && (selection === null || selection.version === null)) {
      setError(new Error(t("s1_need_selection", lang)));
      return;
    }
    setBusy(true);
    try {
      const goalText = description.trim() !== "" ? description.trim() : goal;
      let sessionId: string;
      if (mode === "find" && selection !== null && selection.version !== null) {
        const session = await createSession({
          goal: goalText,
          catalogue: {
            productId: selection.product.product_id,
            version: selection.version,
          },
        });
        sessionId = session.session_id;
        await loadFixtureDocument(sessionId);
      } else if (mode === "upload") {
        const session = await createSession({
          goal: goalText,
          declared: { insurer: declaredInsurer, product: declaredProduct },
        });
        sessionId = session.session_id;
        if (file === null) throw new Error(t("s1_file_required", lang));
        await uploadDocument(sessionId, file);
      } else {
        const session = await createSession({ goal: goalText, useFixture: true });
        sessionId = session.session_id;
        await loadFixtureDocument(sessionId);
      }
      const qs = lang === "hi" ? "?lang=hi" : "";
      router.push(`/evidence/${sessionId}${qs}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  const modes: Array<{ id: IdentifyMode; labelKey: StringKey }> = [
    { id: "find", labelKey: "s1_mode_find" },
    { id: "upload", labelKey: "s1_mode_upload" },
    { id: "sample", labelKey: "s1_mode_sample" },
  ];

  return (
    <>
      {mode !== "upload" ? <FixtureBanner /> : null}
      <div className="page page-narr">
        <h1>{t("s1_title", lang)}</h1>
        <p className="muted" style={{ marginBottom: 24 }}>
          {t("s1_intro", lang)}
        </p>

        {error !== null ? <ErrorBox error={error} lang={lang} onRetry={() => setError(null)} /> : null}

        <div role="radiogroup" aria-label={t("s1_title", lang)}>
          {GOALS.map((g) => (
            <label key={g.id} className={`radio-card${goal === g.id ? " selected" : ""}`}>
              <input
                type="radio"
                name="goal"
                value={g.id}
                checked={goal === g.id}
                onChange={() => setGoal(g.id)}
              />
              <span>{t(g.labelKey, lang)}</span>
              {goal === g.id ? (
                <span className="tick" aria-hidden="true">
                  ✓
                </span>
              ) : null}
            </label>
          ))}
        </div>

        <label className="field-label" htmlFor="describe">
          {t("s1_describe_label", lang)}
        </label>
        <textarea
          id="describe"
          className="full"
          rows={3}
          placeholder={t("s1_describe_placeholder", lang)}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <h2 style={{ marginTop: 32 }}>{t("s1_policy_title", lang)}</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          {t("s1_policy_intro", lang)}
        </p>

        <div role="radiogroup" aria-label={t("s1_policy_title", lang)}>
          {modes.map((m) => (
            <label key={m.id} className={`radio-card${mode === m.id ? " selected" : ""}`}>
              <input
                type="radio"
                name="identify-mode"
                value={m.id}
                checked={mode === m.id}
                onChange={() => setMode(m.id)}
              />
              <span>{t(m.labelKey, lang)}</span>
              {mode === m.id ? (
                <span className="tick" aria-hidden="true">
                  ✓
                </span>
              ) : null}
            </label>
          ))}
        </div>

        {mode === "find" ? (
          <div style={{ marginTop: 16 }}>
            <PolicySearch lang={lang} selection={selection} onSelect={setSelection} />
          </div>
        ) : null}

        {mode === "upload" ? (
          <div style={{ marginTop: 16 }}>
            <label className="field-label" htmlFor="declared-insurer">
              {t("s1_declared_insurer", lang)}
            </label>
            <input
              id="declared-insurer"
              type="text"
              value={declaredInsurer}
              onChange={(e) => setDeclaredInsurer(e.target.value)}
              style={{ width: "100%" }}
            />
            <label className="field-label" htmlFor="declared-product">
              {t("s1_declared_product", lang)}
            </label>
            <input
              id="declared-product"
              type="text"
              value={declaredProduct}
              onChange={(e) => setDeclaredProduct(e.target.value)}
              style={{ width: "100%" }}
            />
            <p className="muted small" style={{ marginTop: 6 }}>
              {t("s1_declared_note", lang)}
            </p>
            <label className="field-label" htmlFor="policy-file">
              {t("s1_upload_label", lang)}
            </label>
            <input
              id="policy-file"
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <p className="muted small" style={{ marginTop: 6 }}>
              {t("s1_upload_hint", lang)}
            </p>
          </div>
        ) : null}

        {mode === "sample" ? (
          <p className="muted small" style={{ marginTop: 12 }}>
            {t("s1_sample_note", lang)}
          </p>
        ) : null}

        <ConsentBlock lang={lang} />

        <div style={{ marginTop: 32 }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || !canStart}
            onClick={() => void start()}
          >
            {busy ? t("s1_starting", lang) : t("s1_start", lang)}
          </button>
          {!canStart && mode === "find" ? (
            <p className="muted small" style={{ marginTop: 8 }}>
              {t("s1_need_selection", lang)}
            </p>
          ) : null}
        </div>
      </div>
    </>
  );
}
