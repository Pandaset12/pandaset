import { useEffect, useState } from "react";
import { ApiError, getLiveQuotes, type LiveQuote } from "../api/portfolio";

export function LiveQuotesPanel({ symbols }: { symbols: string[] }) {
  const [quotes, setQuotes] = useState<LiveQuote[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const symbolKey = symbols.join(",");

  useEffect(() => {
    const requestedSymbols = symbolKey ? symbolKey.split(",") : [];
    let active = true;
    let inFlight = false;
    let timer: number | undefined;
    let retryDelay = 15_000;
    let retryAllowed = true;
    setQuotes([]);
    setError("");
    setDisabled(false);
    setLoading(requestedSymbols.length > 0);
    if (requestedSymbols.length === 0) return;
    const controller = new AbortController();

    const scheduleRefresh = () => {
      if (active && retryAllowed && document.visibilityState === "visible") {
        timer = window.setTimeout(() => void refresh(), retryDelay);
      }
    };

    const refresh = async () => {
      if (
        !active ||
        !retryAllowed ||
        inFlight ||
        document.visibilityState !== "visible"
      )
        return;
      inFlight = true;
      try {
        const result = await getLiveQuotes(requestedSymbols, controller.signal);
        if (active) {
          setQuotes(result.quotes);
          setError("");
          setLoading(false);
          retryDelay = 15_000;
        }
      } catch (cause) {
        if (active) {
          if (
            cause instanceof ApiError &&
            cause.code === "ALPACA_NOT_CONFIGURED"
          ) {
            // Optional feature: no error banner or retries in the default setup.
            retryAllowed = false;
            setDisabled(true);
            setLoading(false);
            return;
          }
          setError(
            cause instanceof ApiError && cause.status === 401
              ? "Sign in again to load live quotes."
              : "Live quotes are temporarily unavailable. Retrying shortly.",
          );
          setLoading(false);
          retryDelay = Math.min(retryDelay * 2, 60_000);
        }
      } finally {
        inFlight = false;
        scheduleRefresh();
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        if (timer !== undefined) window.clearTimeout(timer);
        void refresh();
      } else if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };

    if (requestedSymbols.length > 0) void refresh();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      active = false;
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [symbolKey]);

  if (symbols.length === 0 || disabled) return null;

  return (
    <section className="live-quotes" aria-label="Latest IEX stock prices">
      <div className="live-quotes-heading">
        <strong>Latest available prices</strong>
        <span>
          Alpaca IEX · refreshes every 15 seconds while visible · separate from
          risk calculations
        </span>
      </div>
      {error && (
        <p className="live-quotes-message" role="status">
          {error}
          {quotes.some((quote) => quote.last_price !== null) &&
            " Showing last received prices."}
        </p>
      )}
      <div className="live-quotes-grid">
        {symbols.map((symbol) => {
          const quote = quotes.find((item) => item.symbol === symbol);
          return (
            <div className="live-quote" key={symbol}>
              <strong>{symbol}</strong>
              <span>
                {quote?.last_price == null
                  ? "—"
                  : `$${quote.last_price.toFixed(2)}`}
              </span>
              <small>
                {quote?.last_trade_at
                  ? `Last IEX trade ${new Date(quote.last_trade_at).toLocaleString()}`
                  : loading
                    ? "Loading…"
                    : error
                      ? "Unavailable"
                      : "No IEX trade available"}
              </small>
            </div>
          );
        })}
      </div>
    </section>
  );
}
