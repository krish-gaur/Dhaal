"use client";

import { dec, formatDelta, formatINR } from "@/lib/format";
import type { Lang } from "@/lib/i18n";
import type { WithStatus } from "@/lib/types";
import { StatusDot } from "./StatusDot";

/**
 * The only way a monetary figure reaches the screen: it must arrive with
 * the status of its evidence (F-UI8). `showStatus` renders the label
 * inline; tables that carry a status column set it via the row instead.
 */
export function Money({
  amount,
  lang,
  dp = 0,
  delta = false,
  showStatus = true,
  testId,
}: {
  amount: WithStatus<string>;
  lang: Lang;
  dp?: number;
  delta?: boolean;
  showStatus?: boolean;
  testId?: string;
}) {
  const n = dec(amount.value);
  const text = delta ? formatDelta(n, dp) : formatINR(n, dp);
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <span className="money" data-testid={testId}>
        {text}
      </span>
      {showStatus ? <StatusDot status={amount.status} lang={lang} /> : null}
    </span>
  );
}
