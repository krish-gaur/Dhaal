/**
 * Number formatting for display only.
 *
 * The frontend never computes money — every figure arrives from the API as
 * a Decimal string and is only rendered here. Indian digit grouping via
 * Intl.NumberFormat('en-IN'). Negative amounts use U+2212 (minus sign),
 * never a hyphen-minus.
 */

const MINUS = "−"; // U+2212

function group(amount: number, dp: number): string {
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  }).format(Math.abs(amount));
}

/** ₹ with Indian grouping, e.g. formatINR(120000) === "₹1,20,000". */
export function formatINR(amount: number, dp = 0): string {
  const sign = amount < 0 ? MINUS : "";
  return `${sign}₹${group(amount, dp)}`;
}

/** Dense form for tight spaces, e.g. 120000 → "1.2L", 4500 → "4.5K". */
export function formatINRDense(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? MINUS : "";
  if (abs >= 10000000) return `${sign}${trimNum(abs / 10000000)}Cr`;
  if (abs >= 100000) return `${sign}${trimNum(abs / 100000)}L`;
  if (abs >= 1000) return `${sign}${trimNum(abs / 1000)}K`;
  return `${sign}${abs}`;
}

function trimNum(n: number): string {
  const s = n.toFixed(1);
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

/** Signed delta, e.g. formatDelta(-29167) === "−₹29,167", formatDelta(100) === "+₹100". */
export function formatDelta(amount: number, dp = 0): string {
  if (amount > 0) return `+₹${group(amount, dp)}`;
  if (amount < 0) return `${MINUS}₹${group(amount, dp)}`;
  return `₹${group(0, dp)}`;
}

/** Rate as a percentage, always with " p.a." appended, e.g. "14.42% p.a." */
export function formatPct(rate: number, dp = 2): string {
  return `${(rate * 100).toFixed(dp)}% p.a.`;
}

/** Parse an API Decimal string into a number for display. Throws on garbage. */
export function dec(value: string): number {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    throw new Error(`Not a decimal string: ${value}`);
  }
  return n;
}
