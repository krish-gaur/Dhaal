"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { dec, formatINR } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";
import type { WithStatus } from "@/lib/types";
import { StatusDot } from "./StatusDot";

/**
 * Sticky bottom bar: "You pay" + amount + action.
 * On change, the number counts over 240ms (one of only two animations in
 * the product; disabled under prefers-reduced-motion). A visually hidden
 * aria-live region announces only the final value.
 */
export function VerdictBar({
  oop,
  lang,
  action,
}: {
  oop: WithStatus<string>;
  lang: Lang;
  action?: ReactNode;
}) {
  const target = dec(oop.value);
  const [display, setDisplay] = useState(target);
  const prevRef = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const from = prevRef.current;
    prevRef.current = target;
    if (from === target) {
      setDisplay(target);
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDisplay(target);
      return;
    }
    const start = performance.now();
    const duration = 240;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - p) * (1 - p); // ease-out
      setDisplay(Math.round(from + (target - from) * eased));
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target]);

  return (
    <div className="verdict-bar">
      <div className="verdict-bar-inner">
        <div>
          <span className="vb-label">{t("you_pay", lang)}</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
            <span className="vb-amount" aria-hidden="true" data-testid="verdict-amount">
              {formatINR(display)}
            </span>
            <StatusDot status={oop.status} lang={lang} />
          </span>
          <span
            aria-live="polite"
            style={{
              position: "absolute",
              width: 1,
              height: 1,
              overflow: "hidden",
              clip: "rect(0 0 0 0)",
              whiteSpace: "nowrap",
            }}
          >
            {t("you_pay", lang)} {formatINR(target)}
          </span>
        </div>
        {action}
      </div>
    </div>
  );
}
