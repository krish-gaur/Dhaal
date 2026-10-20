"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FixtureBanner } from "@/components/AppHeader";
import { ClauseRow } from "@/components/ClauseRow";
import type { ClauseAction } from "@/components/ClauseRow";
import { EvidenceViewer } from "@/components/EvidenceViewer";
import { ErrorBox, Loading } from "@/components/States";
import { getClauses, getDocumentPages, getSession, patchClause } from "@/lib/api";
import type { Clause, DocumentPages, SessionDetail } from "@/lib/api";
import { ruleLabel, t } from "@/lib/i18n";
import type { StringKey } from "@/lib/i18n";
import { useLang } from "@/lib/useLang";

const GROUPS: Array<{ id: string; labelKey: StringKey; types: string[] }> = [
  { id: "coverage", labelKey: "s2_group_coverage", types: ["co_payment", "deductible"] },
  { id: "waiting", labelKey: "s2_group_waiting", types: ["waiting_period"] },
  {
    id: "limits",
    labelKey: "s2_group_limits",
    types: ["room_rent_limit", "apportionment_base", "proportionate_deduction"],
  },
  { id: "exclusions", labelKey: "s2_group_exclusions", types: ["non_payable"] },
];

const MATERIAL = ["room_rent_limit", "waiting_period", "non_payable", "apportionment_base"];

/** Screen 2 — Policy evidence: clauses beside the document text that proves them. */
export default function EvidencePage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const { lang } = useLang();
  const router = useRouter();

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [doc, setDoc] = useState<DocumentPages | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [slideOver, setSlideOver] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c, d] = await Promise.all([
        getSession(sessionId),
        getClauses(sessionId),
        getDocumentPages(sessionId).catch(() => null),
      ]);
      setSession(s);
      setClauses(c);
      setDoc(d);
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Deep link from a DeltaChip: /evidence/<id>#<clause_id>
  useEffect(() => {
    if (!clauses) return;
    const hash = window.location.hash.replace("#", "");
    if (hash && clauses.some((c) => c.clause_id === hash)) {
      setSelectedId(hash);
      setExpandedId(hash);
      document.getElementById(hash)?.scrollIntoView({ block: "start" });
    }
  }, [clauses]);

  const selectedClause = useMemo(
    () => clauses?.find((c) => c.clause_id === selectedId) ?? null,
    [clauses, selectedId],
  );

  const undecided = useMemo(() => {
    if (!session) return [];
    return session.material_facts.filter(
      (f) => !["verified", "user_confirmed", "unknown"].includes(f.status),
    );
  }, [session]);

  async function handleAction(clause: Clause, action: ClauseAction) {
    setBusyId(clause.clause_id);
    try {
      if (action.kind === "confirm") {
        await patchClause(sessionId, clause.clause_id, "user_confirmed");
      } else if (action.kind === "unknown") {
        await patchClause(sessionId, clause.clause_id, "unknown");
      } else {
        await patchClause(sessionId, clause.clause_id, "user_confirmed", {
          rule_params: action.params,
        });
      }
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusyId(null);
    }
  }

  if (error !== null && clauses === null) {
    return (
      <div className="page page-narr">
        <h1>{t("s2_title", lang)}</h1>
        <ErrorBox error={error} lang={lang} onRetry={() => void load()} />
      </div>
    );
  }
  if (session === null || clauses === null) {
    return (
      <div className="page">
        <Loading lang={lang} />
      </div>
    );
  }

  const grouped = GROUPS.map((g) => ({
    ...g,
    items: clauses.filter((c) => g.types.includes(c.rule.type)),
  })).filter((g) => g.items.length > 0);
  const rest = clauses.filter((c) => !GROUPS.some((g) => g.types.includes(c.rule.type)));
  if (rest.length > 0) {
    grouped.push({ id: "other", labelKey: "s2_group_other", types: [], items: rest });
  }

  const ready = session.simulation_ready;
  const gateList = undecided.map((f) => ruleLabel(f.rule_type, lang)).join(", ");

  return (
    <>
      {session.mode === "fixture" ? <FixtureBanner /> : null}
      <div className="page" style={{ paddingBottom: 140 }}>
        <h1>{t("s2_title", lang)}</h1>

        {doc ? (
          <p className="muted" style={{ marginBottom: 16 }}>
            {doc.filename} · {t("s2_doc_meta", lang, { pages: doc.page_count })}
          </p>
        ) : null}

        {error !== null ? <ErrorBox error={error} lang={lang} onRetry={() => void load()} /> : null}

        {undecided.length > 0 ? (
          <div className="notice-box" role="note">
            {t("s2_unconfirmed", lang, { count: undecided.length })}{" "}
            <a href="#clauses">{t("s2_review", lang)}</a>
          </div>
        ) : null}

        <div className="evidence-layout">
          <div className="doc-pane-mobile-hidden">
            {doc ? (
              <EvidenceViewer pages={doc.pages} clause={selectedClause} lang={lang} />
            ) : (
              <div className="doc-pane">
                <p className="muted">{t("s2_no_clauses", lang)}</p>
              </div>
            )}
          </div>

          <div id="clauses">
            {clauses.length === 0 ? <p className="muted">{t("s2_no_clauses", lang)}</p> : null}
            {grouped.map((g) => (
              <div key={g.id}>
                <h2 className="group-label">{t(g.labelKey, lang)}</h2>
                {g.items.map((clause) => (
                  <ClauseRow
                    key={clause.clause_id}
                    clause={clause}
                    lang={lang}
                    isMaterial={MATERIAL.includes(clause.rule.type)}
                    busy={busyId === clause.clause_id}
                    expanded={expandedId === clause.clause_id}
                    onToggle={() => {
                      setExpandedId(expandedId === clause.clause_id ? null : clause.clause_id);
                      setSelectedId(clause.clause_id);
                    }}
                    onView={() => {
                      setSelectedId(clause.clause_id);
                      setSlideOver(true);
                    }}
                    onAction={(action) => void handleAction(clause, action)}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {slideOver && doc ? (
        <div className="slide-over" role="dialog" aria-modal="true">
          <div className="slide-over-panel">
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
              <button type="button" className="btn btn-small" onClick={() => setSlideOver(false)}>
                {t("s2_close", lang)}
              </button>
            </div>
            <EvidenceViewer pages={doc.pages} clause={selectedClause} lang={lang} />
          </div>
        </div>
      ) : null}

      <div className="verdict-bar">
        <div className="verdict-bar-inner">
          <span className="small muted" role="status">
            {ready ? "" : t("s2_gate_reason", lang, { list: gateList })}
          </span>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!ready}
            onClick={() =>
              router.push(`/simulate/${sessionId}${lang === "hi" ? "?lang=hi" : ""}`)
            }
          >
            {t("s2_continue", lang)}
          </button>
        </div>
      </div>
    </>
  );
}
