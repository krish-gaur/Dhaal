"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FixtureBanner } from "@/components/AppHeader";
import { ConsentBlock } from "@/components/ConsentBlock";
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

/** Screen 1 — Goal. No hero, no marketing copy: a question and a start button. */
export default function GoalPage() {
  const { lang } = useLang();
  const router = useRouter();
  const [goal, setGoal] = useState<string>(GOALS[0]?.id ?? "hospital_procedure");
  const [description, setDescription] = useState("");
  const [useFixture, setUseFixture] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  async function start() {
    setError(null);
    if (!useFixture && file === null) {
      setError(new Error(t("s1_file_required", lang)));
      return;
    }
    setBusy(true);
    try {
      const goalText = description.trim() !== "" ? description.trim() : goal;
      const session = await createSession(useFixture, goalText);
      if (useFixture) {
        await loadFixtureDocument(session.session_id);
      } else if (file !== null) {
        await uploadDocument(session.session_id, file);
      }
      const qs = lang === "hi" ? "?lang=hi" : "";
      router.push(`/evidence/${session.session_id}${qs}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  return (
    <>
      {useFixture ? <FixtureBanner /> : null}
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

        <div className="switch-row">
          <input
            id="sample-toggle"
            type="checkbox"
            role="switch"
            aria-checked={useFixture}
            checked={useFixture}
            onChange={(e) => setUseFixture(e.target.checked)}
            style={{ width: 20, height: 20 }}
          />
          <label htmlFor="sample-toggle" style={{ fontWeight: 500 }}>
            {t("s1_sample_label", lang)}
          </label>
        </div>
        <p className="muted small">{t("s1_sample_note", lang)}</p>

        {!useFixture ? (
          <div style={{ marginTop: 16 }}>
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

        <ConsentBlock lang={lang} />

        <div style={{ marginTop: 32 }}>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void start()}>
            {busy ? t("s1_starting", lang) : t("s1_start", lang)}
          </button>
        </div>
      </div>
    </>
  );
}
