import { useEffect, useRef, useState } from "react";
import { ArrowPath, ArrowUp, ArrowUpRight, InformationCircle } from "./icons";
import { Modal, PandaMark } from "./UI";
import { assets } from "../../../quant/data";
import { analyze, pct } from "../../../quant/analytics";
export function Analyst({
  weights,
  question,
  onClose,
}: {
  weights: number[];
  question: string;
  onClose: () => void;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; text: string }[]
  >([]);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const metrics = analyze(weights);
  const top = assets[metrics.topRisk];
  function answer(q: string) {
    const lower = q.toLowerCase();
    const asset = assets.find((a) =>
      new RegExp(`\\b${a.symbol.toLowerCase()}\\b`).test(lower),
    );
    if (lower.includes("scenario:"))
      return `${q.replace("Explain this scenario: ", "")}\n\nLower estimated volatility means smaller fluctuations in this sample, not a guarantee of smaller future losses. Compare the return change alongside concentration and the role of the assets you added. The scenario uses the same observations and constant weights for an even comparison.`;
    if (asset) {
      const i = assets.indexOf(asset);
      return `${asset.short} makes up ${weights[i]}% of your portfolio and contributes ${pct(metrics.risk[i])} of estimated volatility.\n\n${asset.thesis}\n\nWatch: ${asset.watch} ${weights[i] === 0 ? "Try adding it in the scenario lab to measure how it changes the portfolio." : "Try changing its allocation in the scenario lab to see the combined effect on risk and return."}`;
    }
    if (/risk|concentrat|volatil|biggest/.test(lower))
      return `${top.short} contributes ${pct(metrics.risk[metrics.topRisk])} of estimated portfolio risk while receiving ${weights[metrics.topRisk]}% of the capital. Risk depends on both an asset’s own volatility and how it moves with the other holdings.\n\nThe portfolio’s annualized volatility is ${pct(metrics.volatility)} in the sample. You can explore the correlation matrix to understand shared exposure, or test a smaller ${top.symbol} allocation in the scenario lab.`;
    if (/return|perform|down|gain|loss/.test(lower)) {
      const i = metrics.contributions.indexOf(
        Math.max(...metrics.contributions),
      );
      return `The sample portfolio returned ${pct(metrics.return)} over the modeled year. ${assets[i].short} contributed the most: ${(metrics.contributions[i] * 100).toFixed(2)} percentage points. The largest peak-to-trough decline was ${pct(metrics.maxDrawdown)}.\n\nThese figures describe the illustrative dataset. They cannot explain a real market move or identify which news caused it.`;
    }
    if (/divers|correl|overlap/.test(lower))
      return `Your portfolio spans ${weights.filter((w) => w > 0).length} holdings and ${metrics.sectors.length} allocation categories. The largest category is ${metrics.sectors[0][0]} at ${pct(metrics.sectors[0][1])}.\n\nDifferent tickers can share the same economic drivers. A broad-market fund can also hold stocks that you own directly. The Risk & exposure page shows return correlations; category totals do not include underlying fund holdings.`;
    return "This guided demo can explain portfolio risk, diversification, sample performance, or the impact of a ticker in the research library. Try “What is my biggest risk?” or “How does MSFT affect my portfolio?” Live Gemini responses are not connected in this interface.";
  }
  function send(q: string) {
    if (!q.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text: q.trim() }]);
    setInput("");
    setBusy(true);
    timer.current = setTimeout(() => {
      setMessages((m) => [...m, { role: "assistant", text: answer(q) }]);
      setBusy(false);
    }, 450);
  }
  useEffect(() => {
    if (question) {
      setMessages([{ role: "user", text: question }]);
      setBusy(true);
      timer.current = setTimeout(() => {
        setMessages([
          { role: "user", text: question },
          { role: "assistant", text: answer(question) },
        ]);
        setBusy(false);
      }, 450);
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []); // Modal is keyed to the requested question.
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);
  return (
    <Modal title="Your portfolio analyst" onClose={onClose}>
      <div className="analyst-mode">
        <InformationCircle size={15} />
        <span>Guided demo · calculated from sample data</span>
      </div>
      <div className="analyst-messages" ref={scroll}>
        {messages.length === 0 && (
          <div className="analyst-welcome">
            <span className="analyst-orb">
              <PandaMark className="analyst-panda-mark" />
            </span>
            <h3>Let’s connect the dots.</h3>
            <p>
              Ask about your holdings, the risks they share, or what drives your
              sample returns.
            </p>
            {[
              "What is my biggest risk?",
              "How diversified is my portfolio?",
              "What drove my portfolio return?",
            ].map((q) => (
              <button onClick={() => send(q)} key={q}>
                {q}
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
        )}
        <div
          className="analyst-conversation"
          role="log"
          aria-label="Portfolio analyst conversation"
          aria-live="polite"
          aria-relevant="additions"
        >
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <span>{m.role === "user" ? "YOU" : "PANDASET"}</span>
              <p>{m.text}</p>
              {m.role === "assistant" && (
                <a href="#/risk" onClick={onClose}>
                  Explore the calculations
                  <ArrowUpRight size={13} />
                </a>
              )}
            </div>
          ))}
        </div>
        {busy && (
          <div className="analyst-loading" role="status">
            <ArrowPath size={15} className="spin" />
            Reading your portfolio…
          </div>
        )}
      </div>
      <form
        className="analyst-input"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          placeholder="Ask about your portfolio…"
          aria-label="Question for portfolio analyst"
          value={input}
          maxLength={600}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          aria-label="Send question"
          disabled={!input.trim() || busy}
        >
          <ArrowUp size={19} />
        </button>
      </form>
      <p className="analyst-footnote">
        Uses calculated metrics and curated explanations. No live AI service.
      </p>
    </Modal>
  );
}
