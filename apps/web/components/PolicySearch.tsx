"use client";

import { useEffect, useRef, useState } from "react";
import { searchCatalogue } from "@/lib/api";
import type { CatalogueProduct } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { Lang } from "@/lib/i18n";

export interface PolicySelection {
  product: CatalogueProduct;
  version: string | null;
}

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "results"; products: CatalogueProduct[]; note: string }
  | { kind: "empty"; note: string }
  | { kind: "error" };

/**
 * Policy autocomplete over the catalogue of wordings Dhaal actually
 * holds. Debounced, keyboard-accessible (arrow keys / Enter / Escape),
 * with explicit loading, empty and error states. Nothing is ever
 * auto-selected: the user must pick a policy AND, when several versions
 * are held, the exact version.
 */
export function PolicySearch({
  lang,
  selection,
  onSelect,
}: {
  lang: Lang;
  selection: PolicySelection | null;
  onSelect: (selection: PolicySelection | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<SearchState>({ kind: "idle" });
  const [activeIndex, setActiveIndex] = useState(-1);
  const seq = useRef(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listId = "policy-search-listbox";

  const products = state.kind === "results" ? state.products : [];

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    const mySeq = ++seq.current;
    setState({ kind: "loading" });
    const timer = setTimeout(() => {
      searchCatalogue(q)
        .then((res) => {
          if (seq.current !== mySeq) return;
          setActiveIndex(-1);
          setState(
            res.results.length > 0
              ? { kind: "results", products: res.results, note: res.note }
              : { kind: "empty", note: res.note },
          );
        })
        .catch(() => {
          if (seq.current === mySeq) setState({ kind: "error" });
        });
    }, 300);
    return () => clearTimeout(timer);
  }, [query, open]);

  function choose(product: CatalogueProduct) {
    const only = product.versions.length === 1 ? product.versions[0] : undefined;
    onSelect({ product, version: only ? only.version : null });
    setOpen(false);
    setQuery("");
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActiveIndex((i) => Math.min(products.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(-1, i - 1));
    } else if (e.key === "Enter") {
      if (open && activeIndex >= 0 && products[activeIndex]) {
        e.preventDefault();
        choose(products[activeIndex]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  if (selection !== null) {
    const { product, version } = selection;
    return (
      <div className="notice-box" role="status">
        <p style={{ margin: "0 0 4px" }}>
          <span className="muted small">{t("s1_policy_selected", lang)}: </span>
          <strong>
            {product.insurer} — {product.product_name}
          </strong>
          {product.fictional ? (
            <span className="badge" style={{ marginLeft: 8 }}>
              {t("s1_fictional_badge", lang)}
            </span>
          ) : null}
          {product.uin ? (
            <span className="muted small" style={{ marginLeft: 8 }}>
              {t("s1_uin", lang, { uin: product.uin })}
            </span>
          ) : null}
        </p>
        {product.versions.length > 1 ? (
          <fieldset style={{ border: "none", padding: 0, margin: "8px 0 0" }}>
            <legend className="small" style={{ marginBottom: 6 }}>
              {t("s1_version_label", lang)}
            </legend>
            {product.versions.map((v) => (
              <label
                key={v.version}
                className={`radio-card${version === v.version ? " selected" : ""}`}
              >
                <input
                  type="radio"
                  name="policy-version"
                  value={v.version}
                  checked={version === v.version}
                  onChange={() => onSelect({ product, version: v.version })}
                />
                <span>
                  {v.version}
                  {v.effective_date ? (
                    <span className="muted small">
                      {" "}
                      · {t("s1_effective_from", lang, { date: v.effective_date })}
                    </span>
                  ) : null}
                </span>
                {version === v.version ? (
                  <span className="tick" aria-hidden="true">
                    ✓
                  </span>
                ) : null}
              </label>
            ))}
          </fieldset>
        ) : version ? (
          <p className="small muted" style={{ margin: "4px 0 0" }}>
            {t("s2_prov_version", lang, { version })}
            {product.versions[0]?.effective_date
              ? ` · ${t("s1_effective_from", lang, { date: product.versions[0].effective_date })}`
              : ""}
          </p>
        ) : null}
        <button
          type="button"
          className="btn btn-small"
          style={{ marginTop: 10 }}
          onClick={() => {
            onSelect(null);
            setState({ kind: "idle" });
          }}
        >
          {t("s1_change_policy", lang)}
        </button>
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <label className="field-label" htmlFor="policy-search">
        {t("s1_search_label", lang)}
      </label>
      <input
        id="policy-search"
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={
          activeIndex >= 0 ? `policy-option-${activeIndex}` : undefined
        }
        autoComplete="off"
        placeholder={t("s1_search_placeholder", lang)}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          // Delay so a click on an option registers first.
          setTimeout(() => setOpen(false), 150);
        }}
        onKeyDown={onKeyDown}
        style={{ width: "100%" }}
      />
      <p className="muted small" style={{ marginTop: 6 }}>
        {t("s1_search_hint", lang)}
      </p>

      {open ? (
        <div
          className="search-dropdown"
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            marginTop: 4,
            background: "var(--color-surface, #fff)",
            maxHeight: 320,
            overflowY: "auto",
          }}
        >
          {state.kind === "loading" ? (
            <p className="muted small" style={{ padding: "10px 12px", margin: 0 }}>
              {t("s1_searching", lang)}
            </p>
          ) : null}
          {state.kind === "error" ? (
            <p className="small" style={{ padding: "10px 12px", margin: 0 }} role="alert">
              {t("s1_search_error", lang)}{" "}
              <button
                type="button"
                className="btn btn-small"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setQuery(query + "");
                  setOpen(true);
                  inputRef.current?.focus();
                }}
              >
                {t("retry", lang)}
              </button>
            </p>
          ) : null}
          {state.kind === "empty" ? (
            <p className="muted small" style={{ padding: "10px 12px", margin: 0 }}>
              {t("s1_search_empty", lang)}
            </p>
          ) : null}
          {state.kind === "results" ? (
            <>
              <ul role="listbox" id={listId} style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {products.map((prod, i) => (
                  <li
                    key={prod.product_id}
                    id={`policy-option-${i}`}
                    role="option"
                    aria-selected={i === activeIndex}
                    className={i === activeIndex ? "search-option active" : "search-option"}
                    style={{
                      padding: "10px 12px",
                      cursor: "pointer",
                      background: i === activeIndex ? "var(--color-hover, #f3f4f6)" : undefined,
                    }}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => choose(prod)}
                    onMouseEnter={() => setActiveIndex(i)}
                  >
                    <span style={{ fontWeight: 500 }}>{prod.product_name}</span>
                    <span className="muted small"> · {prod.insurer}</span>
                    {prod.fictional ? (
                      <span className="badge" style={{ marginLeft: 8 }}>
                        {t("s1_fictional_badge", lang)}
                      </span>
                    ) : null}
                    <span className="muted small" style={{ display: "block" }}>
                      {prod.versions.map((v) => v.version).join(" · ")}
                      {prod.uin ? ` · ${t("s1_uin", lang, { uin: prod.uin })}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="muted small" style={{ padding: "8px 12px", margin: 0 }}>
                {state.note}
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
