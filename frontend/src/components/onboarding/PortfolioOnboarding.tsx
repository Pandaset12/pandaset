import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { Portfolio, PortfolioInput } from "../../api/portfolio";
import {
  ArrowPath,
  ArrowRight,
  Check,
  InformationCircle,
  RectangleStack,
  XMark,
} from "../icons";
import { TickerSearch } from "./TickerSearch";
import type { SearchTickers } from "./TickerSearch";
import { LandingPanda } from "../LandingPanda";
import {
  MAX_HOLDINGS,
  MAX_NAME_LENGTH,
  PERCENT_SCALE,
  formatPercentage,
  parsePercentage,
  portfolioNameError,
  validatePortfolioDraft,
} from "./portfolioDraft";
import type { HoldingDraft, TickerResult } from "./portfolioDraft";

export type PortfolioOnboardingProps = {
  /** Key the component by the signed-in investor's user ID. */
  loadState?: "loading" | "empty" | "error";
  hasExistingPortfolios?: boolean;
  maxHoldings?: number;
  allowDirectEntry?: boolean;
  onRetryLoad?: () => void;
  searchTickers: SearchTickers;
  createPortfolio: (
    input: PortfolioInput,
    options: { signal: AbortSignal },
  ) => Promise<Portfolio>;
  onOpenPortfolio: (portfolio: Portfolio) => void;
  onCancel?: () => void;
};
type Step = "welcome" | "name" | "holdings" | "review";
const steps = [
  ["Name your portfolio", "Give your investments a home."],
  ["Add your holdings", "Choose tickers and their weights."],
  ["Review & create", "Make sure everything adds up."],
];

export function PortfolioOnboarding({
  loadState = "empty",
  hasExistingPortfolios = false,
  maxHoldings = MAX_HOLDINGS,
  allowDirectEntry = true,
  onRetryLoad,
  searchTickers,
  createPortfolio,
  onOpenPortfolio,
  onCancel,
}: PortfolioOnboardingProps) {
  const prefix = useId();
  const [step, setStep] = useState<Step>("welcome");
  const [name, setName] = useState("");
  const [holdings, setHoldings] = useState<HoldingDraft[]>([]);
  const [showNameError, setShowNameError] = useState(false);
  const [showHoldingErrors, setShowHoldingErrors] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [saveErrorDetail, setSaveErrorDetail] = useState("");
  const [created, setCreated] = useState<Portfolio | null>(null);
  const [focusTarget, setFocusTarget] = useState("");
  const title = useRef<HTMLHeadingElement>(null);
  const pending = useRef<AbortController | null>(null);
  const validation = validatePortfolioDraft(name, holdings, maxHoldings);
  const currentStep = step === "name" ? 0 : step === "holdings" ? 1 : 2;
  const tickerInputId = prefix + "-search";
  const weightId = (symbol: string) => prefix + "-weight-" + symbol;

  useEffect(
    () => () => {
      pending.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (loadState !== "empty") {
      pending.current?.abort();
      pending.current = null;
      setSaving(false);
    }
  }, [loadState]);
  useEffect(() => {
    if (step !== "welcome" || created) title.current?.focus();
  }, [step, created]);
  useEffect(() => {
    if (focusTarget) {
      document.getElementById(focusTarget)?.focus();
      setFocusTarget("");
    }
  }, [focusTarget, holdings.length]);

  function addHolding(ticker: TickerResult) {
    if (
      holdings.length >= maxHoldings ||
      holdings.some((row) => row.symbol === ticker.symbol)
    )
      return;
    setHoldings((previous) => [...previous, { ...ticker, percentage: "" }]);
    setFocusTarget(weightId(ticker.symbol));
  }
  function removeHolding(symbol: string) {
    const remaining = holdings.filter((row) => row.symbol !== symbol);
    setHoldings(remaining);
    setFocusTarget(
      remaining.length
        ? weightId(remaining[remaining.length - 1].symbol)
        : tickerInputId,
    );
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    if (step === "name") {
      if (portfolioNameError(name)) {
        setShowNameError(true);
        setFocusTarget(prefix + "-name");
      } else {
        setName(name.trim());
        setStep("holdings");
      }
      return;
    }
    if (step === "holdings") {
      setShowHoldingErrors(true);
      if (validation.payload) {
        setSaveError(false);
        setStep("review");
      } else {
        const firstInvalid = holdings.find(
          (row) => validation.errors.rows[row.symbol],
        );
        setFocusTarget(
          firstInvalid
            ? weightId(firstInvalid.symbol)
            : !holdings.length
              ? tickerInputId
              : prefix + "-allocation",
        );
      }
      return;
    }
    if (step !== "review" || !validation.payload) return;
    const controller = new AbortController();
    pending.current = controller;
    setSaving(true);
    setSaveError(false);
    try {
      const portfolio = await createPortfolio(validation.payload, {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (
        !portfolio?.portfolio_id ||
        typeof portfolio.name !== "string" ||
        !Array.isArray(portfolio.holdings)
      )
        throw new Error("Invalid saved portfolio response.");
      setCreated(portfolio);
    } catch (error) {
      if (!controller.signal.aborted) {
        setSaveError(true);
        setSaveErrorDetail(
          error instanceof Error
            ? error.message
            : "Try again or change your holdings.",
        );
      }
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        if (!controller.signal.aborted) setSaving(false);
      }
    }
  }

  const intro = (
    <aside className="po-intro" aria-label="Portfolio setup steps">
      <h1>
        Your investments,
        <br />
        <em>in focus.</em>
      </h1>
      <p>
        A clearer picture starts with what you own. Bring your holdings
        together, then explore them with Pandaset.
      </p>
      <ol className="po-steps">
        {steps.map(([label, description], index) => {
          const done =
            Boolean(created) || (step !== "welcome" && currentStep > index);
          const active =
            !created && step !== "welcome" && currentStep === index;
          return (
            <li
              key={label}
              className={done ? "done" : active ? "current" : ""}
              aria-current={active ? "step" : undefined}
            >
              <span className="po-step-number" aria-hidden="true">
                {done ? <Check size={16} /> : "0" + (index + 1)}
              </span>
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </li>
          );
        })}
      </ol>
      <div className="po-intro-note">
        <InformationCircle size={17} aria-hidden="true" />
        <p>
          Start with the stocks and funds you own. You’ll enter their share of
          your total portfolio value.
        </p>
      </div>
      {onCancel && (
        <button
          className="po-back-link"
          type="button"
          onClick={onCancel}
          disabled={saving}
        >
          Back to portfolios
        </button>
      )}
    </aside>
  );

  if (loadState !== "empty")
    return (
      <section className="portfolio-onboarding">
        {intro}
        <div
          className="po-panel po-state"
          role={loadState === "loading" ? "status" : "alert"}
          aria-live="polite"
        >
          <div className="po-state-illustration" aria-hidden="true">
            <LandingPanda />
            {loadState === "loading" && (
              <ArrowPath size={19} className="po-state-spinner po-spin" />
            )}
          </div>
          <h2>
            {loadState === "loading"
              ? "Finding your portfolios…"
              : "Your portfolios couldn’t load."}
          </h2>
          <p>
            {loadState === "loading"
              ? "Getting your workspace ready."
              : "We couldn’t check your saved portfolios. Try again to pick up where you left off."}
          </p>
          {loadState === "error" && onRetryLoad && (
            <button className="button dark" type="button" onClick={onRetryLoad}>
              Try again <ArrowPath size={16} aria-hidden="true" />
            </button>
          )}
        </div>
      </section>
    );

  if (created)
    return (
      <section className="portfolio-onboarding">
        {intro}
        <div className="po-panel po-state">
          <div className="po-state-illustration" aria-hidden="true">
            <LandingPanda />
            <span className="po-state-success-mark">
              <Check size={16} />
            </span>
          </div>
          <h2 ref={title} tabIndex={-1}>
            Your portfolio is ready.
          </h2>
          <p>
            <strong>{created.name}</strong> has been created with{" "}
            {created.holdings.length}{" "}
            {created.holdings.length === 1 ? "holding" : "holdings"}.
          </p>
          <button
            className="button dark"
            type="button"
            onClick={() => onOpenPortfolio(created)}
          >
            Open portfolio <ArrowRight size={17} aria-hidden="true" />
          </button>
        </div>
      </section>
    );

  if (step === "welcome")
    return (
      <section className="portfolio-onboarding">
        {intro}
        <div className="po-panel po-welcome">
          <div className="po-empty-mascot" aria-hidden="true">
            <LandingPanda />
          </div>
          <h2>
            {hasExistingPortfolios
              ? "Start another portfolio."
              : "No portfolios yet."}
            <br />
            Plenty of possibilities.
          </h2>
          <p>
            Add your holdings and set their weights.
            <br />
            Your allocation is the starting point for every insight.
          </p>
          <button
            className="button dark"
            type="button"
            onClick={() => setStep("name")}
          >
            {hasExistingPortfolios
              ? "Create another portfolio"
              : "Create your first portfolio"}{" "}
            <ArrowRight size={17} aria-hidden="true" />
          </button>
          <span className="po-welcome-caption">
            Your tickers. Your allocation. Your perspective.
          </span>
        </div>
      </section>
    );

  const hasRowErrors = Object.keys(validation.errors.rows).length > 0;
  const total = validation.totalUnits / PERCENT_SCALE;
  const allocationMessage = hasRowErrors
    ? "Enter a valid weight for each holding."
    : validation.errors.total ||
      (holdings.length
        ? "Fully allocated. Ready to review."
        : "Your weights will add up here.");

  return (
    <section className="portfolio-onboarding">
      {intro}
      <form
        className="po-panel po-form"
        onSubmit={(event) => void submit(event)}
        noValidate
        aria-busy={saving}
      >
        <div className="po-panel-heading">
          <span className="po-step-count">STEP {currentStep + 1} OF 3</span>
        </div>
        <h2 ref={title} tabIndex={-1}>
          {step === "name"
            ? "Give it a name."
            : step === "holdings"
              ? "What do you own?"
              : "A look at the whole picture."}
        </h2>
        <p className="po-description">
          {step === "name"
            ? "Choose a name you’ll recognize. You can create more portfolios later."
            : step === "holdings"
              ? "Add your stocks and funds, then enter each holding’s weight."
              : "Check your holdings and allocation before creating your portfolio."}
        </p>

        {step === "name" && (
          <div className="po-name-step">
            <label htmlFor={prefix + "-name"}>Portfolio name</label>
            <input
              id={prefix + "-name"}
              value={name}
              maxLength={MAX_NAME_LENGTH}
              autoComplete="off"
              placeholder="e.g. Long-term investments"
              aria-invalid={showNameError && Boolean(validation.errors.name)}
              aria-describedby={prefix + "-name-help"}
              onChange={(event) => setName(event.target.value)}
            />
            <p
              id={prefix + "-name-help"}
              className={
                showNameError && validation.errors.name
                  ? "po-field-error"
                  : "po-help"
              }
              role={
                showNameError && validation.errors.name ? "alert" : undefined
              }
            >
              {(showNameError && validation.errors.name) ||
                "A personal label for this group of investments."}
            </p>
            <div className="po-name-note">
              <RectangleStack size={22} aria-hidden="true" />
              <div>
                <strong>One portfolio, one clear picture.</strong>
                <p>
                  Keep related investments together. You can separate different
                  goals into their own portfolios.
                </p>
              </div>
            </div>
          </div>
        )}

        {step === "holdings" && (
          <div className="po-holdings-step">
            <TickerSearch
              inputId={tickerInputId}
              selectedSymbols={holdings.map((row) => row.symbol)}
              searchTickers={searchTickers}
              allowDirectEntry={allowDirectEntry}
              onSelect={addHolding}
              disabled={holdings.length >= maxHoldings}
            />
            {holdings.length >= maxHoldings && (
              <p className="po-help" role="status">
                You’ve reached the limit of {maxHoldings} holdings.
              </p>
            )}
            <div className="po-holdings-heading">
              <span>HOLDING</span>
              <span>WEIGHT</span>
              <span className="sr-only">Remove</span>
            </div>
            {!holdings.length && (
              <div className="po-no-holdings">
                <RectangleStack size={24} aria-hidden="true" />
                <p>Start with your first ticker.</p>
                <small>Your holdings will appear here.</small>
              </div>
            )}
            <div className="po-holdings-list">
              {holdings.map((holding, index) => {
                const error = showHoldingErrors
                  ? validation.errors.rows[holding.symbol]
                  : undefined;
                return (
                  <div key={holding.symbol} className="po-holding-row">
                    <div className="po-holding-identity">
                      <span
                        className={"po-ticker-mark po-tone-" + (index % 4)}
                        aria-hidden="true"
                      >
                        {holding.symbol.slice(0, 1)}
                      </span>
                      <span>
                        <strong>{holding.symbol}</strong>
                        <small>
                          {holding.name || "Unverified exact ticker"}
                        </small>
                      </span>
                    </div>
                    <div className="po-weight-field">
                      <label
                        htmlFor={weightId(holding.symbol)}
                        className="sr-only"
                      >
                        {holding.symbol} weight (%)
                      </label>
                      <div
                        className={
                          "po-percentage-input" + (error ? " invalid" : "")
                        }
                      >
                        <input
                          id={weightId(holding.symbol)}
                          value={holding.percentage}
                          inputMode="decimal"
                          type="text"
                          maxLength={16}
                          placeholder="0"
                          aria-invalid={Boolean(error)}
                          aria-describedby={
                            error
                              ? weightId(holding.symbol) + "-error"
                              : prefix + "-weight-help"
                          }
                          onChange={(event) =>
                            setHoldings((previous) =>
                              previous.map((row) =>
                                row.symbol === holding.symbol
                                  ? { ...row, percentage: event.target.value }
                                  : row,
                              ),
                            )
                          }
                        />
                        <span aria-hidden="true">%</span>
                      </div>
                    </div>
                    <button
                      className="po-remove"
                      type="button"
                      aria-label={"Remove " + holding.symbol}
                      onClick={() => removeHolding(holding.symbol)}
                    >
                      <XMark size={17} aria-hidden="true" />
                    </button>
                    {error && (
                      <p
                        id={weightId(holding.symbol) + "-error"}
                        className="po-field-error po-row-error"
                      >
                        {error}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            <div
              id={prefix + "-allocation"}
              className={
                "po-allocation" + (validation.payload ? " complete" : "")
              }
              tabIndex={-1}
            >
              <div>
                <span>Total allocation</span>
                <strong>
                  {formatPercentage(validation.totalUnits)}
                  <small> / 100%</small>
                </strong>
              </div>
              <div
                className="po-meter"
                role="meter"
                aria-label="Total allocation"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.min(total, 100)}
                aria-valuetext={
                  formatPercentage(validation.totalUnits) + " percent allocated"
                }
              >
                <span style={{ width: Math.min(total, 100) + "%" }} />
              </div>
              <p aria-live="polite">{allocationMessage}</p>
            </div>
            {showHoldingErrors && validation.errors.holdings && (
              <p className="po-field-error" role="alert">
                {validation.errors.holdings}
              </p>
            )}
            <details className="po-weight-help" id={prefix + "-weight-help"}>
              <summary>How do I work out my weights?</summary>
              <p>
                Divide each holding’s current value by your total portfolio
                value, then multiply by 100. For example, $250 in a $1,000
                portfolio is 25%. Use up to 6 decimal places.
              </p>
            </details>
          </div>
        )}

        {step === "review" && (
          <div className="po-review">
            <div className="po-review-name">
              <span>PORTFOLIO NAME</span>
              <strong>{name.trim()}</strong>
            </div>
            <div className="po-review-title">
              <span>
                {holdings.length}{" "}
                {holdings.length === 1 ? "holding" : "holdings"}
              </span>
              <span>
                <Check size={14} aria-hidden="true" />
                100% allocated
              </span>
            </div>
            <div className="po-allocation-strip" aria-hidden="true">
              {holdings.map((holding, index) => (
                <span
                  key={holding.symbol}
                  className={"po-tone-" + (index % 4)}
                  style={{
                    width:
                      (parsePercentage(holding.percentage) || 0) /
                        PERCENT_SCALE +
                      "%",
                  }}
                />
              ))}
            </div>
            <ul className="po-review-list" aria-label="Holdings to create">
              {holdings.map((holding, index) => (
                <li key={holding.symbol}>
                  <span
                    className={"po-review-dot po-tone-" + (index % 4)}
                    aria-hidden="true"
                  />
                  <span>
                    <strong>{holding.symbol}</strong>
                    <small>{holding.name || "Unverified exact ticker"}</small>
                  </span>
                  <strong>
                    {formatPercentage(parsePercentage(holding.percentage) || 0)}
                    %
                  </strong>
                </li>
              ))}
            </ul>
            <p className="po-review-note">
              <InformationCircle size={16} aria-hidden="true" />
              Market-data availability is checked before your portfolio is
              saved. Manually entered tickers must match exchange symbols.
            </p>
            {saveError && (
              <div className="po-save-error" role="alert">
                <strong>We couldn’t create your portfolio.</strong>
                <p>
                  {saveErrorDetail} Your entries are still here. Try again, or
                  go back to make changes.
                </p>
              </div>
            )}
            {saving && (
              <p className="po-saving-status" role="status">
                Creating your portfolio…
              </p>
            )}
          </div>
        )}
        <div className="po-form-actions">
          <button
            className="po-back-link"
            type="button"
            disabled={saving}
            onClick={() => {
              setSaveError(false);
              setStep(
                step === "name"
                  ? "welcome"
                  : step === "holdings"
                    ? "name"
                    : "holdings",
              );
            }}
          >
            Back
          </button>
          <button
            className="button dark"
            type="submit"
            disabled={saving || (step === "review" && !validation.payload)}
          >
            {saving
              ? "Creating…"
              : step === "review"
                ? "Create portfolio"
                : step === "holdings"
                  ? "Review portfolio"
                  : "Continue"}
            {saving ? (
              <ArrowPath size={17} className="po-spin" aria-hidden="true" />
            ) : (
              <ArrowRight size={17} aria-hidden="true" />
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
