"use client";

import type { Estimate } from "@/lib/api";
import { dec, formatINR } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import type { ScenarioState } from "@/lib/scenario";

/**
 * The three scenario controls: room category, continuity credit, bill
 * amount. Presentational — Screen 3 owns state, fetching, and the
 * changed-field count that gates single-clause attribution (F-CF1).
 */
export function TogglePanel({
  estimate,
  scenario,
  changedCount,
  lang,
  onChange,
}: {
  estimate: Estimate;
  scenario: ScenarioState;
  changedCount: number;
  lang: Lang;
  onChange: (next: ScenarioState) => void;
}) {
  const capRate = estimate.room_cap_per_day;
  const billedRate = estimate.room_rate_per_night;

  return (
    <div className="toggle-panel">
      <div className="toggle-row">
        <span id="room-label">{t("s3_room_label", lang)}</span>
        {capRate !== null ? (
          <span className="seg-control" role="group" aria-labelledby="room-label">
            <button
              type="button"
              aria-pressed={!scenario.roomAtCap}
              onClick={() => onChange({ ...scenario, roomAtCap: false })}
            >
              {t("s3_room_above", lang, { rate: formatINR(dec(billedRate)) })}
            </button>
            <button
              type="button"
              aria-pressed={scenario.roomAtCap}
              onClick={() => onChange({ ...scenario, roomAtCap: true })}
              data-testid="room-at-cap"
            >
              {t("s3_room_at", lang, { rate: formatINR(dec(capRate)) })}
            </button>
          </span>
        ) : (
          <span className="muted small">{t("s3_room_unknown", lang)}</span>
        )}
      </div>

      <div className="toggle-row">
        <span id="continuity-label">{t("s3_continuity_label", lang)}</span>
        <span className="seg-control" role="group" aria-labelledby="continuity-label">
          <button
            type="button"
            aria-pressed={scenario.continuityConfirmed}
            onClick={() => onChange({ ...scenario, continuityConfirmed: true })}
          >
            {t("s3_continuity_on", lang)}
          </button>
          <button
            type="button"
            aria-pressed={!scenario.continuityConfirmed}
            onClick={() => onChange({ ...scenario, continuityConfirmed: false })}
            data-testid="continuity-off"
          >
            {t("s3_continuity_off", lang)}
          </button>
        </span>
      </div>

      <div className="toggle-row">
        <label htmlFor="bill-amount">{t("s3_bill_label", lang)}</label>
        <input
          id="bill-amount"
          type="number"
          min={0}
          step={500}
          value={scenario.grossBill}
          onChange={(e) => onChange({ ...scenario, grossBill: e.target.value })}
          style={{ width: 160 }}
        />
      </div>

      {changedCount > 1 ? (
        <p className="muted small" style={{ marginTop: 12 }} data-testid="multi-change">
          {t("s3_multi_change", lang, { count: changedCount })}
        </p>
      ) : null}
    </div>
  );
}
