"use client";

import type { ClauseStatus } from "@/lib/api";
import { statusLabel } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

/** 6×6px square (never a circle) + uppercase label. Status is never colour alone. */
const COLORS: Record<ClauseStatus, { fill: string; border: string }> = {
  verified: { fill: "#2F6B4F", border: "#2F6B4F" },
  unverified: { fill: "#8A877C", border: "#8A877C" },
  unknown: { fill: "#B4762A", border: "#B4762A" },
  conflicting: { fill: "#A8322D", border: "#A8322D" },
  user_confirmed: { fill: "#1F4E79", border: "#1F4E79" },
  synthetic: { fill: "transparent", border: "#8A877C" },
};

export function StatusDot({ status, lang }: { status: ClauseStatus; lang: Lang }) {
  const c = COLORS[status];
  return (
    <span className="status-dot">
      <span
        className="sq"
        aria-hidden="true"
        style={{ background: c.fill, border: `1px solid ${c.border}` }}
      />
      {statusLabel(status, lang)}
    </span>
  );
}
