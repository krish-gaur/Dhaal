"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FixtureBanner } from "@/components/AppHeader";
import { Money } from "@/components/Money";
import { ErrorBox, Loading } from "@/components/States";
import { StatusDot } from "@/components/StatusDot";
import { deleteSession, getAudit } from "@/lib/api";
import type { Audit, ClauseStatus, DeleteResult } from "@/lib/api";
import { statusLabel, t } from "@/lib/i18n";
import { useLang } from "@/lib/useLang";
import { withStatus } from "@/lib/types";

/** Screen 5 — Your data: transparency record and verified deletion. */
export default function AuditPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params);
  const { lang } = useLang();

  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState<DeleteResult | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    try {
      setAudit(await getAudit(sessionId));
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (modalOpen) inputRef.current?.focus();
  }, [modalOpen]);

  // Minimal focus trap for the delete modal.
  function onModalKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      setModalOpen(false);
      return;
    }
    if (e.key !== "Tab" || !modalRef.current) return;
    const focusables = modalRef.current.querySelectorAll<HTMLElement>(
      "button, input, [href], textarea, select",
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }

  async function doDelete() {
    setDeleting(true);
    try {
      const res = await deleteSession(sessionId);
      setDeleted(res);
      setModalOpen(false);
    } catch (e) {
      setError(e);
      setModalOpen(false);
    } finally {
      setDeleting(false);
    }
  }

  if (deleted !== null) {
    return (
      <div className="page page-narr">
        <h1>{t("s5_deleted_title", lang)}</h1>
        <p role="status">
          {t("s5_deleted_counts", lang, {
            documents: deleted.counts["documents"] ?? 0,
            clauses: deleted.counts["clauses"] ?? 0,
            runs: deleted.counts["runs"] ?? 0,
          })}
        </p>
        <div className="nav-row">
          <Link href="/" className="btn btn-primary">
            {t("s5_start_again", lang)}
          </Link>
        </div>
      </div>
    );
  }

  if (error !== null && audit === null) {
    return (
      <div className="page page-narr">
        <h1>{t("s5_title", lang)}</h1>
        <ErrorBox error={error} lang={lang} onRetry={() => void load()} />
      </div>
    );
  }
  if (audit === null) {
    return (
      <div className="page">
        <Loading lang={lang} />
      </div>
    );
  }

  const runStatus: ClauseStatus = audit.mode === "fixture" ? "synthetic" : "unverified";

  return (
    <>
      {audit.mode === "fixture" ? <FixtureBanner /> : null}
      <div className="page" style={{ maxWidth: 860 }}>
        <h1>{t("s5_title", lang)}</h1>

        {error !== null ? <ErrorBox error={error} lang={lang} onRetry={() => void load()} /> : null}

        <h2>{t("s5_data_title", lang)}</h2>
        {audit.document ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("s5_col_item", lang)}</th>
                  <th scope="col">{t("s5_col_detail", lang)}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">{t("s5_row_document", lang)}</th>
                  <td>
                    {audit.document.filename} ({audit.document.page_count}{" "}
                    {t("s2_doc_meta", lang, { pages: audit.document.page_count })})
                  </td>
                </tr>
                {audit.policy?.insurer || audit.policy?.product_name ? (
                  <tr>
                    <th scope="row">{t("s2_policy_block_title", lang)}</th>
                    <td>
                      {[audit.policy?.insurer, audit.policy?.product_name]
                        .filter(Boolean)
                        .join(" — ")}
                      {audit.policy?.version
                        ? ` · ${t("s2_prov_version", lang, { version: audit.policy.version })}`
                        : ""}
                      {audit.policy?.uin
                        ? ` · ${t("s1_uin", lang, { uin: audit.policy.uin })}`
                        : ""}
                      {audit.policy?.fictional
                        ? ` (${t("s1_fictional_badge", lang)})`
                        : ""}
                    </td>
                  </tr>
                ) : null}
                <tr>
                  <th scope="row">{t("s5_row_purpose", lang)}</th>
                  <td>{t("s5_purpose_text", lang)}</td>
                </tr>
                {audit.document.provenance ? (
                  <>
                    <tr>
                      <th scope="row">SHA-256</th>
                      <td style={{ wordBreak: "break-all" }}>
                        {audit.document.provenance.sha256 ?? "—"}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">{t("s5_row_source", lang)}</th>
                      <td>
                        {audit.document.provenance.source_kind === "catalogue_document"
                          ? t("s2_source_catalogue", lang)
                          : t("s2_source_upload", lang)}
                        {audit.document.provenance.effective_date
                          ? ` · ${t("s2_prov_effective", lang, {
                              date: audit.document.provenance.effective_date,
                            })}`
                          : ""}
                        {audit.document.provenance.retrieved_at
                          ? ` · ${audit.document.provenance.retrieved_at.slice(0, 19).replace("T", " ")}`
                          : ""}
                      </td>
                    </tr>
                  </>
                ) : null}
                <tr>
                  <th scope="row">{t("s5_row_pages", lang)}</th>
                  <td>{audit.document.pages_read}</td>
                </tr>
                <tr>
                  <th scope="row">{t("s5_row_retention", lang)}</th>
                  <td>{audit.document.retention}</td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{t("s5_no_document", lang)}</p>
        )}

        <h2>{t("s5_clauses_title", lang)}</h2>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {Object.entries(audit.clauses_by_status).map(([status, count]) => (
            <li key={status} style={{ padding: "4px 0" }}>
              <StatusDot status={status as ClauseStatus} lang={lang} />{" "}
              <span className="muted">
                {statusLabel(status, lang)}: {count}
              </span>
            </li>
          ))}
        </ul>

        <h2>{t("s5_engine_title", lang)}</h2>
        <p>
          {t("s5_engine_version", lang)}: <span className="mono">{audit.engine_version}</span>
        </p>
        <p className="muted">{t("s5_repro", lang)}</p>

        <h3>{t("s5_runs_title", lang)}</h3>
        {audit.runs.length > 0 ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("s5_run_when", lang)}</th>
                  <th scope="col">{t("s5_run_hash", lang)}</th>
                  <th scope="col" className="money-cell">
                    {t("s5_run_insurer", lang)}
                  </th>
                  <th scope="col" className="money-cell">
                    {t("s5_run_you", lang)}
                  </th>
                  <th scope="col">{t("s5_run_checks", lang)}</th>
                </tr>
              </thead>
              <tbody>
                {audit.runs.map((run) => (
                  <tr key={run.run_id}>
                    <td className="small">{run.created_at}</td>
                    <td className="mono">{run.run_hash}</td>
                    <td className="money-cell">
                      {run.insurer_payment !== null ? (
                        <Money amount={withStatus(run.insurer_payment, runStatus)} lang={lang} showStatus={false} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="money-cell">
                      {run.out_of_pocket !== null ? (
                        <Money amount={withStatus(run.out_of_pocket, runStatus)} lang={lang} showStatus={false} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="small">{run.invariants_ok ? t("s5_checks_ok", lang) : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">{t("s5_no_runs", lang)}</p>
        )}

        <h2>{t("s5_ai_title", lang)}</h2>
        <p>{audit.provider_disclosure}</p>

        <h2>{t("s5_delete_title", lang)}</h2>
        <p className="muted">{t("s5_delete_text", lang)}</p>
        <button type="button" className="btn btn-danger" onClick={() => setModalOpen(true)}>
          {t("s5_delete_button", lang)}
        </button>

        <p className="footer-disclaimer">{t("s4_disclaimer", lang)}</p>
      </div>

      {modalOpen ? (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-title"
            ref={modalRef}
            onKeyDown={onModalKeyDown}
          >
            <h2 id="delete-title" style={{ marginTop: 0 }}>
              {t("s5_delete_title", lang)}
            </h2>
            <p className="muted">{t("s5_delete_text", lang)}</p>
            <label className="field-label" htmlFor="delete-confirm">
              {t("s5_delete_prompt", lang)}
            </label>
            <input
              id="delete-confirm"
              ref={inputRef}
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
              style={{ width: "100%" }}
            />
            <div className="nav-row">
              <button
                type="button"
                className="btn btn-danger"
                disabled={confirmText !== "DELETE" || deleting}
                onClick={() => void doDelete()}
              >
                {t("s5_delete_confirm", lang)}
              </button>
              <button type="button" className="btn" onClick={() => setModalOpen(false)}>
                {t("s5_cancel", lang)}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
