"use client";

import Link from "next/link";
import { t } from "@/lib/i18n";
import { useLang } from "@/lib/useLang";

export function AppHeader() {
  const { lang, setLang } = useLang();
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Link href="/" className="wordmark">
          <span className="devanagari">ढाल</span> {t("app_name", lang)}
        </Link>
        <div className="lang-toggle" role="group" aria-label={t("s5_language", lang)}>
          <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>
            English
          </button>
          <button type="button" aria-pressed={lang === "hi"} onClick={() => setLang("hi")}>
            हिंदी
          </button>
        </div>
      </div>
    </header>
  );
}

/** Always visible in fixture mode, never dismissible (NF: fixture banner). */
export function FixtureBanner() {
  const { lang } = useLang();
  return (
    <div className="fixture-banner" role="note">
      <div className="fixture-banner-inner">{t("fixture_banner", lang)}</div>
    </div>
  );
}
