import { describe, expect, it } from "vitest";
import { formatDelta, formatINR, formatINRDense, formatPct } from "./format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR(120000)).toBe("₹1,20,000");
    expect(formatINR(38667)).toBe("₹38,667");
    expect(formatINR(9500)).toBe("₹9,500");
    expect(formatINR(81333)).toBe("₹81,333");
    expect(formatINR(300000)).toBe("₹3,00,000");
    expect(formatINR(10000000)).toBe("₹1,00,00,000");
    expect(formatINR(0)).toBe("₹0");
    expect(formatINR(999)).toBe("₹999");
  });

  it("uses U+2212 for negatives, never a hyphen", () => {
    const s = formatINR(-4201.25, 2);
    expect(s).toBe("−₹4,201.25");
    expect(s).not.toContain("-");
    expect(s.charCodeAt(0)).toBe(0x2212);
  });

  it("supports paise for EMI figures", () => {
    expect(formatINR(4001.25, 2)).toBe("₹4,001.25");
  });
});

describe("formatDelta", () => {
  it("signs deltas with + and U+2212", () => {
    expect(formatDelta(-29167)).toBe("−₹29,167");
    expect(formatDelta(81333)).toBe("+₹81,333");
    expect(formatDelta(0)).toBe("₹0");
  });
});

describe("formatPct", () => {
  it("always appends p.a.", () => {
    expect(formatPct(0.1442)).toBe("14.42% p.a.");
    expect(formatPct(0.1953)).toBe("19.53% p.a.");
  });
});

describe("formatINRDense", () => {
  it("compacts large values", () => {
    expect(formatINRDense(120000)).toBe("1.2L");
    expect(formatINRDense(-6000)).toBe("−6K");
    expect(formatINRDense(10000)).toBe("10K");
  });
});
