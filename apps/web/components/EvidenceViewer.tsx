"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Clause } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

/**
 * Renders the policy's extracted page text (not an image) with the
 * selected clause's quote highlighted at its verified character offsets.
 * Highlight: pale background + 2px underline. No glow, no pulse.
 */
export function EvidenceViewer({
  pages,
  clause,
  lang,
}: {
  pages: string[];
  clause: Clause | null;
  lang: Lang;
}) {
  const clausePage = clause?.page ?? 1;
  const [page, setPage] = useState(clausePage);
  const markRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setPage(clausePage);
  }, [clausePage, clause?.clause_id]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center" });
  }, [page, clause?.clause_id]);

  const text = pages[page - 1] ?? "";
  const parts = useMemo(() => {
    if (
      clause &&
      clause.page === page &&
      clause.char_start !== null &&
      clause.char_end !== null &&
      clause.char_start >= 0 &&
      clause.char_end <= text.length &&
      clause.char_start < clause.char_end
    ) {
      return {
        before: text.slice(0, clause.char_start),
        hit: text.slice(clause.char_start, clause.char_end),
        after: text.slice(clause.char_end),
      };
    }
    return { before: text, hit: "", after: "" };
  }, [clause, page, text]);

  return (
    <div className="doc-pane">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <span className="small muted">
          {t("s2_page_label", lang, { page, total: pages.length })}
        </span>
        <span style={{ display: "inline-flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-small"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← {t("s2_prev_page", lang)}
          </button>
          <button
            type="button"
            className="btn btn-small"
            disabled={page >= pages.length}
            onClick={() => setPage((p) => Math.min(pages.length, p + 1))}
          >
            {t("s2_next_page", lang)} →
          </button>
        </span>
      </div>
      <div className="page-text">
        {parts.before}
        {parts.hit ? <mark ref={markRef}>{parts.hit}</mark> : null}
        {parts.after}
      </div>
    </div>
  );
}
