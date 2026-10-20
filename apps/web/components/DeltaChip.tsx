"use client";

import { dec, formatDelta } from "@/lib/format";

/**
 * The effect of a single changed variable, as computed by the server's
 * counterfactual endpoint. Amount in --color-conflict, U+2212 for
 * negatives. Clicking jumps to the clause behind it.
 */
export function DeltaChip({
  oopDelta,
  text,
  onClick,
}: {
  oopDelta: string;
  text: string;
  onClick?: () => void;
}) {
  return (
    <button type="button" className="delta-chip" onClick={onClick} data-testid="delta-chip">
      <span className="delta-amount">{formatDelta(dec(oopDelta))}</span>
      <span>{text}</span>
    </button>
  );
}
