import { useEffect, useState } from "react";
import { ApiError, getLiveQuotes, type LiveQuote } from "../api/portfolio";

export function LiveQuotesPanel({ symbols }: { symbols: string[] }) {
  const [quotes, setQuotes] = useState<LiveQuote[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const symbolKey = symbols.join(",");

  useEffect(() => {
    const requestedSymbols = symbolKey ? symbolKey.split(",") : [];
    let active = true;
    let inFlight = false;
    let timer: number | undefined;
    let retryDelay = 15_000;
    setQuotes([]);
    setError("");
    setLoading(requestedSymbols.length > 0);

    const scheduleRefresh = () => {
      if (active && document.visibilityState === "visible") {
        timer = window.setTimeout(() => void refresh(), retryDelay);
      }
    };

    const refresh = async () => {
      if (!active || inFlight || document.visibilityState !== "visible") return;
      inFlight = true;
      try {
        const result = await getLiveQuotes(requestedSymbols);
        if (active) {
          setQuotes(result.quotes);
          setError("");
          setLoading(false);
          retryDelay = 15_000;
        }
      } catch (cause) {
        if (active) {
          setError(
            cause instanceof ApiError
              ? cause.message
              : "Live quotes are temporarily unavailable.",
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
      if (timer !== undefined) window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [symbolKey]);

  if (symbols.length === 0) return null;

  return (
    <section className="live-quotes" aria-label="Latest IEX stock prices">
      <div className="live-quotes-heading">
        <strong>Latest available prices</strong>
        <span>Alpaca IEX · auto-refresh every 15 seconds · separate from risk calculations</span>
      </div>
      {error && <p className="live-quotes-message" role="status">{error}</p>}
      <div className="live-quotes-grid">
        {symbols.map((symbol) => {
          const quote = quotes.find((item) => item.symbol === symbol);
          return (
            <div className="live-quote" key={symbol}>
              <strong>{symbol}</strong>
              <span>{quote?.last_price == null ? "—" : `$${quote.last_price.toFixed(2)}`}</span>
              <small>
                {quote?.last_trade_at
                  ? `Last IEX trade ${new Date(quote.last_trade_at).toLocaleString()}`
                  : loading
                    ? "Loading…"
                    : error
                      ? "Unavailable"
                      : "No recent IEX trade"}
              </small>
            </div>
          );
        })}
      </div>
    </section>
  );
}
