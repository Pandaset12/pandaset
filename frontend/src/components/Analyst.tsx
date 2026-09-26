import { useEffect, useRef, useState } from "react";
import { ArrowPath, ArrowUp, ArrowUpRight, InformationCircle } from "./icons";
import { Modal, PandaMark } from "./UI";
import {
  askPortfolio,
  createRequestGuard,
  type AnalysisResponse,
  type AskResponse,
} from "../api/portfolio";

type Message =
  | { role: "user"; text: string }
  | {
      role: "assistant";
      text: string;
      response?: AskResponse;
      error?: string;
      question?: string;
    };

export function Analyst({
  portfolioId,
  analysis,
  question,
  onClose,
}: {
  portfolioId: string;
  analysis: AnalysisResponse;
  question: string;
  onClose: () => void;
}) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const requestId = useRef(createRequestGuard());
  const autoQuestionSent = useRef(false);

  async function send(value: string, retry = false) {
    const text = value.trim();
    if (!text || busy) return;
    if (!retry) setMessages((items) => [...items, { role: "user", text }]);
    setInput("");
    setBusy(true);
    const id = requestId.current.begin();
    try {
      const response = await askPortfolio(
        portfolioId,
        analysis.analysis_id,
        text,
      );
      if (requestId.current.isCurrent(id))
        setMessages((items) => [
          ...items,
          { role: "assistant", text: response.answer, response },
        ]);
    } catch (error) {
      if (requestId.current.isCurrent(id))
        setMessages((items) => [
          ...items,
          {
            role: "assistant",
            text: "The explanation could not be loaded.",
            error:
              error instanceof Error
                ? error.message
                : "Ask Panda is unavailable.",
            question: text,
          },
        ]);
    } finally {
      if (requestId.current.isCurrent(id)) setBusy(false);
    }
  }

  useEffect(() => {
    if (question && !autoQuestionSent.current) {
      autoQuestionSent.current = true;
      void send(question);
    }
    return () => {
      requestId.current.invalidate();
    };
  }, []);
  useEffect(() => {
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, busy]);

  return (
    <Modal
      title="Your portfolio analyst"
      onClose={busy ? () => undefined : onClose}
    >
      <div className="analyst-mode">
        <InformationCircle size={15} />
        <span>
          Using saved analysis {analysis.analysis_id} ·{" "}
          {analysis.data_mode === "demo" ? "sample data" : "live data"}
        </span>
      </div>
      <div className="analyst-messages" ref={scroll}>
        {messages.length === 0 && (
          <div className="analyst-welcome">
            <span className="analyst-orb">
              <PandaMark className="analyst-panda-mark" />
            </span>
            <h3>Let’s connect the dots.</h3>
            <p>Ask about the metrics in this saved portfolio analysis.</p>
            {[
              "What is my biggest risk?",
              "How diversified is my portfolio?",
              "What does this analysis show?",
            ].map((suggestion) => (
              <button onClick={() => void send(suggestion)} key={suggestion}>
                {suggestion}
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
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <span>{message.role === "user" ? "YOU" : "PANDASET"}</span>
              <p>{message.text}</p>
              {message.role === "assistant" && message.response && (
                <div className="ask-response-details">
                  <span className="label-chip">
                    {message.response.status === "demo"
                      ? "DEMO RESPONSE"
                      : message.response.status.toUpperCase()}
                  </span>
                  {message.response.citations.length > 0 && (
                    <div>
                      <strong>Metric citations</strong>
                      <ul>
                        {message.response.citations.map((citation) => (
                          <li key={citation.field}>
                            {citation.field}: {citation.value.toFixed(4)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {message.response.warnings.map((warning) => (
                    <p className="small-text muted" key={warning}>
                      {warning}
                    </p>
                  ))}
                  <p className="small-text muted">
                    {message.response.disclaimer}
                  </p>
                </div>
              )}
              {message.role === "assistant" && message.error && (
                <>
                  <p className="field-error" role="alert">
                    {message.error}
                  </p>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => void send(message.question ?? "", true)}
                  >
                    Retry
                    <ArrowPath size={14} />
                  </button>
                </>
              )}
              {message.role === "assistant" && !message.error && (
                <a href="#/risk" onClick={busy ? undefined : onClose}>
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
            Reading the saved analysis…
          </div>
        )}
      </div>
      <form
        className="analyst-input"
        onSubmit={(event) => {
          event.preventDefault();
          void send(input);
        }}
      >
        <input
          placeholder="Ask about your portfolio…"
          aria-label="Question for portfolio analyst"
          value={input}
          maxLength={600}
          onChange={(event) => setInput(event.target.value)}
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
        Answers use the saved backend snapshot. Review its status, citations,
        warnings, and disclaimer.
      </p>
    </Modal>
  );
}
