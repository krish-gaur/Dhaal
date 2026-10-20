"use client";

import Link from "next/link";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

/** Loading, error and not-found states shared by every screen. No fake spinners. */

export function Loading({ lang }: { lang: Lang }) {
  return (
    <p className="loading-line" role="status">
      {t("loading", lang)}
    </p>
  );
}

export function ErrorBox({
  error,
  lang,
  onRetry,
}: {
  error: unknown;
  lang: Lang;
  onRetry?: () => void;
}) {
  const is404 = error instanceof ApiError && error.code === 404;
  const message =
    error instanceof ApiError
      ? error.message
      : error instanceof Error
        ? error.message
        : String(error);
  return (
    <div className="error-box" role="alert">
      <p style={{ fontWeight: 500, marginBottom: 4 }}>{t("error_title", lang)}</p>
      <p className="muted" style={{ marginBottom: 12 }}>
        {is404 ? t("session_not_found", lang) : message}
      </p>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {onRetry && !is404 ? (
          <button type="button" className="btn btn-small" onClick={onRetry}>
            {t("retry", lang)}
          </button>
        ) : null}
        <Link href="/" className="btn btn-small">
          {t("back_home", lang)}
        </Link>
      </div>
    </div>
  );
}
