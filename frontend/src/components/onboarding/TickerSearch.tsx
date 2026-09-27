import { useEffect, useId, useRef, useState } from "react";
import { ArrowPath, MagnifyingGlass, Plus } from "../icons";
import {
  isValidSymbol,
  normalizeSymbol,
  normalizeTickerResults,
} from "./portfolioDraft";
import type { TickerResult } from "./portfolioDraft";

export type SearchTickers = (
  query: string,
  options: { signal: AbortSignal },
) => Promise<TickerResult[]>;

type Props = {
  inputId: string;
  selectedSymbols: string[];
  searchTickers: SearchTickers;
  onSelect: (ticker: TickerResult) => void;
  disabled?: boolean;
  allowDirectEntry?: boolean;
};

export function TickerSearch({
  inputId,
  selectedSymbols,
  searchTickers,
  onSelect,
  disabled = false,
  allowDirectEntry = true,
}: Props) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TickerResult[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const text = query.trim();
    setResults([]);
    setActive(-1);
    if (!text || disabled) {
      setStatus("idle");
      return () => controller.abort();
    }
    setStatus("loading");
    const timer = window.setTimeout(() => {
      void Promise.resolve()
        .then(() => searchTickers(text, { signal: controller.signal }))
        .then((found) => {
          if (controller.signal.aborted) return;
          setResults(normalizeTickerResults(found));
          setStatus("ready");
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setStatus("error");
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query, searchTickers, disabled]);

  const manualSymbol = normalizeSymbol(query);
  const options = [...results];
  const canAddManual =
    allowDirectEntry &&
    status !== "loading" &&
    isValidSymbol(manualSymbol) &&
    !results.some((result) => result.symbol === manualSymbol);
  if (canAddManual) options.push({ symbol: manualSymbol });
  const expanded = open && Boolean(query.trim()) && !disabled;

  useEffect(() => {
    if (expanded && active >= 0)
      document.getElementById(listId + "-" + active)?.scrollIntoView({
        block: "nearest",
      });
  }, [active, expanded, listId]);

  function select(index: number) {
    const option = options[index];
    if (!option || selectedSymbols.includes(option.symbol)) return;
    onSelect(option);
    setQuery("");
    setResults([]);
    setOpen(false);
    setActive(-1);
  }

  function move(direction: number) {
    if (!options.length) return;
    let next = active < 0 && direction < 0 ? 0 : active;
    for (let attempt = 0; attempt < options.length; attempt += 1) {
      next = (next + direction + options.length) % options.length;
      if (!selectedSymbols.includes(options[next].symbol)) {
        setActive(next);
        return;
      }
    }
  }

  return (
    <div
      className="po-search"
      ref={root}
      onBlur={(event) => {
        if (!root.current?.contains(event.relatedTarget as Node))
          setOpen(false);
      }}
    >
      <label htmlFor={inputId}>Add a holding</label>
      <div className="po-search-input">
        <MagnifyingGlass size={18} aria-hidden="true" />
        <input
          id={inputId}
          value={query}
          disabled={disabled}
          placeholder="Search a ticker or company"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={expanded ? listId : undefined}
          aria-activedescendant={
            expanded && active >= 0 ? listId + "-" + active : undefined
          }
          aria-describedby={inputId + "-help"}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              setActive(-1);
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setOpen(true);
              move(event.key === "ArrowDown" ? 1 : -1);
            }
            if (event.key === "Enter") {
              event.preventDefault();
              if (expanded)
                select(
                  active >= 0
                    ? active
                    : options.findIndex(
                        (option) => !selectedSymbols.includes(option.symbol),
                      ),
                );
            }
          }}
        />
        {status === "loading" && (
          <ArrowPath className="po-spin" size={16} aria-hidden="true" />
        )}
      </div>
      <p id={inputId + "-help"} className="po-help">
        {allowDirectEntry
          ? "Search by name, or add a ticker directly. Use arrows and Enter to select."
          : "Search supported instruments. Use arrows and Enter to select."}
      </p>
      {expanded && (
        <div className="po-search-menu">
          <div className="po-search-notice" role="status">
            {status === "loading"
              ? "Searching tickers…"
              : status === "error"
                ? allowDirectEntry
                  ? "Search is unavailable. You can still add a ticker directly."
                  : "Search is unavailable. Try again in a moment."
                : !results.length
                  ? allowDirectEntry
                    ? "No matching companies found. Check the ticker before adding it."
                    : "No supported instruments match this search."
                  : results.length +
                    (results.length === 1 ? " match" : " matches")}
          </div>
          <ul id={listId} role="listbox" aria-label="Ticker results">
            {options.map((option, index) => {
              const exists = selectedSymbols.includes(option.symbol);
              const manual = canAddManual && index === options.length - 1;
              return (
                <li
                  id={listId + "-" + index}
                  key={option.symbol}
                  role="option"
                  aria-selected={active === index}
                  aria-disabled={exists}
                  className={active === index ? "active" : ""}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => {
                    if (!exists) setActive(index);
                  }}
                  onClick={() => select(index)}
                >
                  <span className="po-result-symbol">{option.symbol}</span>
                  <span className="po-result-name">
                    {manual ? "Add ticker directly" : option.name || "Ticker"}
                  </span>
                  {exists ? (
                    <small>Added</small>
                  ) : (
                    <Plus size={16} aria-hidden="true" />
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
