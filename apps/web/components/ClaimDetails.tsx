"use client";

import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import { elapsedFromDates } from "@/lib/scenario";
import type { ClaimState } from "@/lib/scenario";

/**
 * Condition tags the held wordings enumerate (specified-disease lists
 * and permanent exclusions). The engine matches waiting periods and
 * exclusions against these tags — never against free text.
 */
const CONDITIONS: Array<{ tag: string; label: string }> = [
  { tag: "gallbladder_cholecystectomy", label: "Gallbladder stones / cholecystectomy" },
  { tag: "cataract", label: "Cataract" },
  { tag: "hernia", label: "Hernia" },
  { tag: "hydrocele", label: "Hydrocele" },
  { tag: "hysterectomy_nonmalignant", label: "Hysterectomy (non-malignant)" },
  { tag: "kidney_stones_lithotripsy", label: "Kidney stones / lithotripsy" },
  { tag: "benign_prostatic_hypertrophy", label: "Benign prostatic hypertrophy" },
  { tag: "varicose_veins", label: "Varicose veins" },
  { tag: "sinusitis", label: "Sinusitis" },
  { tag: "joint_replacement", label: "Joint replacement" },
  { tag: "bariatric_surgery", label: "Bariatric (weight-loss) surgery" },
  { tag: "cosmetic_treatment", label: "Cosmetic treatment" },
  { tag: "dental_treatment", label: "Dental treatment" },
  { tag: "experimental_treatment", label: "Experimental treatment" },
  { tag: "self_inflicted_injury", label: "Self-inflicted injury" },
  { tag: "substance_dependency_treatment", label: "Substance-dependency treatment" },
];

const UNSURE = "__unsure__";
const OTHER = "other_condition";

/**
 * Claim facts form: condition, pre-existing flag, accident flag, and
 * the policy-history dates. Anything left unsure is sent as null and
 * comes back visibly unresolved — never guessed.
 */
export function ClaimDetails({
  claim,
  lang,
  onChange,
}: {
  claim: ClaimState;
  lang: Lang;
  onChange: (next: ClaimState) => void;
}) {
  const conditionValue = claim.conditionTag ?? UNSURE;
  const elapsed = elapsedFromDates(
    claim.inceptionDate,
    claim.admissionDate,
    claim.continuityCreditMonths,
  );

  const triState = (
    label: string,
    value: boolean | null,
    set: (v: boolean | null) => void,
    name = "tri",
  ) => (
    <div className="toggle-row">
      <span id={`${name}-label`}>{label}</span>
      <span className="seg-control" role="group" aria-labelledby={`${name}-label`}>
        <button type="button" aria-pressed={value === true} onClick={() => set(true)}>
          {t("s3_yes", lang)}
        </button>
        <button type="button" aria-pressed={value === false} onClick={() => set(false)}>
          {t("s3_no", lang)}
        </button>
        <button type="button" aria-pressed={value === null} onClick={() => set(null)}>
          {t("s3_unsure", lang)}
        </button>
      </span>
    </div>
  );

  return (
    <div className="toggle-panel">
      <div className="toggle-row">
        <label htmlFor="claim-condition">{t("s3_condition_label", lang)}</label>
        <select
          id="claim-condition"
          value={conditionValue}
          onChange={(e) =>
            onChange({
              ...claim,
              conditionTag: e.target.value === UNSURE ? null : e.target.value,
            })
          }
        >
          <option value={UNSURE}>{t("s3_condition_unsure", lang)}</option>
          {CONDITIONS.map((c) => (
            <option key={c.tag} value={c.tag}>
              {c.label}
            </option>
          ))}
          <option value={OTHER}>{t("s3_condition_other", lang)}</option>
        </select>
      </div>

      {triState(t("s3_ped_label", lang), claim.preExisting, (v) =>
        onChange({ ...claim, preExisting: v }),
      )}

      <div className="toggle-row">
        <span id="claim-accident-label">{t("s3_accident_label", lang)}</span>
        <span className="seg-control" role="group" aria-labelledby="claim-accident-label">
          <button
            type="button"
            aria-pressed={claim.accident}
            onClick={() => onChange({ ...claim, accident: true })}
          >
            {t("s3_yes", lang)}
          </button>
          <button
            type="button"
            aria-pressed={!claim.accident}
            onClick={() => onChange({ ...claim, accident: false })}
          >
            {t("s3_no", lang)}
          </button>
        </span>
      </div>

      <div className="toggle-row">
        <label htmlFor="claim-inception">{t("s3_inception_label", lang)}</label>
        <input
          id="claim-inception"
          type="date"
          value={claim.inceptionDate ?? ""}
          onChange={(e) =>
            onChange({ ...claim, inceptionDate: e.target.value || null })
          }
        />
      </div>

      <div className="toggle-row">
        <label htmlFor="claim-admission">{t("s3_admission_label", lang)}</label>
        <input
          id="claim-admission"
          type="date"
          value={claim.admissionDate ?? ""}
          onChange={(e) =>
            onChange({ ...claim, admissionDate: e.target.value || null })
          }
        />
      </div>

      <div className="toggle-row">
        <label htmlFor="claim-credit">{t("s3_credit_label", lang)}</label>
        <input
          id="claim-credit"
          type="number"
          min={0}
          max={600}
          step={1}
          value={claim.continuityCreditMonths}
          onChange={(e) => {
            const n = Number(e.target.value);
            onChange({
              ...claim,
              continuityCreditMonths: Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0,
            });
          }}
          style={{ width: 110 }}
        />
      </div>

      {elapsed !== null ? (
        <p className="muted small" role="status">
          {t("s3_dates_derived", lang, { months: elapsed.months, days: elapsed.days })}
        </p>
      ) : null}
    </div>
  );
}
