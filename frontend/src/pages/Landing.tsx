import { useEffect, useRef, useState } from "react";
import { PandaMark } from "../components/UI";
import { useLandingMotion } from "../hooks/useLandingMotion";
import { LandingPanda } from "../components/LandingPanda";
import { analyze, pct } from "../../../quant/analytics";
import { assets, initialWeights } from "../../../quant/data";

const sample = analyze(initialWeights);
const topRisk = assets[sample.topRisk];
const demo = "./app.html#/";
function Arrow() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      aria-hidden="true"
    >
      <path d="M5 12h14m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
function DemoLink({ light = false }: { light?: boolean }) {
  return (
    <a className={`lp-button ${light ? "lp-button-light" : ""}`} href={demo}>
      Explore the demo <Arrow />
    </a>
  );
}

export default function Landing() {
  const root = useRef<HTMLDivElement>(null);
  useLandingMotion(root);
  const mounted = useRef(false);
  const manualPerspective = useRef(false);
  const [perspective, setPerspective] = useState<"capital" | "risk">("capital");
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    if (root.current && !mounted.current) {
      mounted.current = true;
      window.ScrollCraft.mount(root.current);
    }
  }, []);
  useEffect(() => {
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    const update = () => {
      if (manualPerspective.current || motion.matches || innerWidth <= 760)
        return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const section = document.getElementById("perspective");
        if (!section) return;
        const rect = section.getBoundingClientRect();
        const travel = Math.max(1, rect.height - innerHeight);
        if (rect.top <= 0 && rect.bottom >= innerHeight) {
          setPerspective(-rect.top / travel >= 0.4 ? "risk" : "capital");
        }
      });
    };
    addEventListener("scroll", update, { passive: true });
    return () => {
      removeEventListener("scroll", update);
      cancelAnimationFrame(frame);
    };
  }, []);
  const choosePerspective = (value: "capital" | "risk") => {
    manualPerspective.current = true;
    setPerspective(value);
  };
  const goTo = (id: string) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    setMenuOpen(false);
    const target = document.getElementById(id);
    target?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
    target?.focus({ preventScroll: true });
  };
  return (
    <div className="panda-landing" ref={root}>
      <a className="lp-skip" href="#main" onClick={goTo("main")}>
        Skip to content
      </a>
      <header className="lp-header">
        <a className="lp-brand" href="./" aria-label="Pandaset home">
          <PandaMark />
          <span>Pandaset</span>
        </a>
        <button
          className="lp-menu-button"
          aria-expanded={menuOpen}
          aria-controls="landing-nav"
          onClick={() => setMenuOpen(!menuOpen)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setMenuOpen(false);
          }}
        >
          {menuOpen ? "Close" : "Menu"}
        </button>
        <nav
          id="landing-nav"
          className={menuOpen ? "lp-nav is-open" : "lp-nav"}
          aria-label="Landing navigation"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setMenuOpen(false);
              document
                .querySelector<HTMLButtonElement>(".lp-menu-button")
                ?.focus();
            }
          }}
        >
          <a href="#perspective" onClick={goTo("perspective")}>
            The perspective
          </a>
          <a href="#toolkit" onClick={goTo("toolkit")}>
            The toolkit
          </a>
          <a className="lp-nav-cta" href={demo}>
            Explore the demo <Arrow />
          </a>
        </nav>
      </header>
      <main id="main" tabIndex={-1}>
        <section
          className="lp-hero lp-wrap"
          data-sc-act="flow"
          aria-labelledby="hero-heading"
        >
          <div className="lp-hero-copy">
            <p className="lp-kicker">
              <span /> A LITTLE PERSPECTIVE. A LOT MORE CLARITY.
            </p>
            <h1 id="hero-heading">
              Less noise.
              <br />
              <span>More insight.</span>
            </h1>
            <p className="lp-hero-description">
              Get to know what you own.
              <br />
              Explore your portfolio, understand its risk, and ask better
              questions.
            </p>
            <DemoLink />
          </div>
          <div className="lp-scene">
            <div
              className="lp-orbit"
              data-sc-parallax="-0.35"
              aria-hidden="true"
            >
              <span />
              <span />
              <span />
            </div>
            <div
              className="lp-scene-grid"
              aria-hidden="true"
              data-sc-parallax="-0.15"
            />
            <div className="lp-mascot-plane" data-sc-parallax="0.5">
              <div className="lp-panda-arrival">
                <LandingPanda />
              </div>
            </div>
            <div
              className="lp-paper-plane"
              data-sc-parallax="1.1"
              aria-hidden="true"
            >
              <div className="lp-paper">
                <span>THE BIGGER PICTURE</span>
                <svg viewBox="0 0 370 125" fill="none">
                  <path d="M0 30h370M0 65h370M0 100h370" stroke="#e4e4e4" />
                  <g className="lp-chart-ink">
                    <path
                      d="m0 100 28-9 27 5 26-31 27 10 28-26 27 8 27-29 29 9 28-22 29 7 30-17 39 4"
                      stroke="#171717"
                      strokeWidth="3"
                      strokeLinejoin="round"
                    />
                    <circle
                      className="lp-chart-tip"
                      cx="345"
                      cy="14"
                      r="5"
                      fill="#171717"
                    />
                  </g>
                </svg>
                <div>
                  <span>Zoom out.</span>
                  <span>See what matters.</span>
                </div>
              </div>
            </div>
            <span className="lp-scene-caption">
              A curious mind. A clearer view.
            </span>
          </div>
          <div className="lp-hero-bottom">
            <span>YOUR PORTFOLIO, FROM EVERY ANGLE</span>
            <div>
              <span>Performance</span>
              <i /> <span>Risk</span>
              <i /> <span>Research</span>
              <i /> <span>What-if</span>
            </div>
          </div>
        </section>
        <section
          className="lp-recognition lp-wrap"
          data-sc-act="flow"
          aria-labelledby="recognition-heading"
        >
          <PandaMark className="lp-small-panda" />
          <h2 id="recognition-heading">
            {"Owning investments is one thing."
              .split(" ")
              .map((word, index) => (
                <span key={index} className="lp-recognition-word">
                  {word}{" "}
                </span>
              ))}
            <br />
            {"Understanding them is another.".split(" ").map((word, index) => (
              <span key={index} className="lp-recognition-word">
                {word}
                {index < 3 ? " " : ""}
              </span>
            ))}
          </h2>
          <p>
            A list of tickers only tells part of the story. Pandaset connects
            the dots between what you hold, how it behaves, and what could
            change.
          </p>
        </section>
        <section
          id="perspective"
          tabIndex={-1}
          className="lp-perspective"
          data-sc-act="pin"
          data-sc-span="1.8"
          aria-labelledby="perspective-heading"
        >
          <div data-sc-stage className="lp-perspective-stage">
            <div className="lp-perspective-inner lp-wrap">
              <div className="lp-perspective-copy">
                <p className="lp-kicker">THROUGH PANDA’S EYES</p>
                <h2 id="perspective-heading">
                  Same portfolio.
                  <br />
                  <span>
                    A different
                    <br className="lp-desktop-break" /> perspective.
                  </span>
                </h2>
                <p>
                  Where your money sits and where your risk comes from can tell
                  very different stories.
                </p>
                <div
                  className="lp-eye-controls"
                  role="group"
                  aria-label="Chart perspective"
                >
                  <button
                    aria-pressed={perspective === "capital"}
                    onClick={() => choosePerspective("capital")}
                  >
                    <span className="lp-eye">
                      <i />
                    </span>
                    <span>Capital</span>
                  </button>
                  <button
                    aria-pressed={perspective === "risk"}
                    onClick={() => choosePerspective("risk")}
                  >
                    <span className="lp-eye">
                      <i />
                    </span>
                    <span>Risk</span>
                  </button>
                </div>
                <p className="lp-control-hint">
                  Choose an eye. See the difference.
                </p>
              </div>
              <div className="lp-chart-panel">
                <div className="lp-chart-heading">
                  <h3>
                    {perspective === "capital"
                      ? "Where the money sits"
                      : "Where the risk comes from"}
                  </h3>
                  <span>ILLUSTRATIVE SAMPLE</span>
                </div>
                <div
                  className="lp-bars"
                  role="img"
                  aria-label={`${perspective === "capital" ? "Capital allocation" : "Modeled risk contribution"}: ${assets
                    .flatMap((asset, i) =>
                      initialWeights[i] > 0
                        ? [
                            `${asset.symbol} ${pct(perspective === "capital" ? initialWeights[i] / 100 : sample.risk[i])}`,
                          ]
                        : [],
                    )
                    .join(", ")}`}
                >
                  {assets.map(
                    (asset, index) =>
                      initialWeights[index] > 0 && (
                        <div className="lp-bar-row" key={asset.symbol}>
                          <span>{asset.symbol}</span>
                          <div className="lp-bar-track">
                            <div
                              className="lp-bar"
                              style={{
                                transform: `scaleX(${perspective === "capital" ? initialWeights[index] / 100 : sample.risk[index]})`,
                              }}
                            />
                          </div>
                          <span>
                            {pct(
                              perspective === "capital"
                                ? initialWeights[index] / 100
                                : sample.risk[index],
                            )}
                          </span>
                        </div>
                      ),
                  )}
                </div>
                <div className="lp-chart-takeaway" aria-live="polite">
                  <span className="lp-plus">+</span>
                  <p>
                    {perspective === "capital" ? (
                      <>
                        <strong>
                          {topRisk.short} holds {initialWeights[sample.topRisk]}
                          % of the capital.
                        </strong>{" "}
                        Switch to risk to see how much it contributes to the
                        portfolio’s modeled volatility.
                      </>
                    ) : (
                      <>
                        <strong>
                          {topRisk.short} contributes{" "}
                          {pct(sample.risk[sample.topRisk])} of modeled risk.
                        </strong>{" "}
                        An allocation’s size is only one part of its influence
                        on a portfolio.
                      </>
                    )}
                  </p>
                </div>
                <p className="lp-chart-note">
                  Calculated from the demo’s synthetic returns. Risk
                  contribution is a share of portfolio variance, not a
                  prediction of loss. Negative contributions offset modeled
                  variance.
                </p>
              </div>
            </div>
          </div>
        </section>
        <section
          id="toolkit"
          tabIndex={-1}
          className="lp-toolkit lp-wrap"
          data-sc-act="flow"
          aria-labelledby="toolkit-heading"
        >
          <div className="lp-toolkit-heading">
            <h2 id="toolkit-heading">
              Follow your
              <br />
              <span>curiosity.</span>
            </h2>
            <p>
              One shared portfolio.
              <br />
              Four ways to make sense of it.
            </p>
          </div>
          <div
            className="lp-tool-list"
            data-sc-reveal="up"
            data-sc-reveal-at="0.05 0.3"
          >
            <a href={demo} data-lp-arrival>
              <span className="lp-tool-symbol" aria-hidden="true">
                ↗
              </span>
              <div>
                <h3>See the whole picture</h3>
                <p>Performance, holdings, and what is driving the returns.</p>
              </div>
              <span className="lp-tool-name">Overview</span>
              <Arrow />
            </a>
            <a href="./app.html#/risk" data-lp-arrival>
              <span className="lp-tool-symbol" aria-hidden="true">
                ◎
              </span>
              <div>
                <h3>Look beneath the surface</h3>
                <p>
                  Concentration, correlations, and the sources of portfolio
                  risk.
                </p>
              </div>
              <span className="lp-tool-name">Risk & exposure</span>
              <Arrow />
            </a>
            <a href="./app.html#/research" data-lp-arrival>
              <span
                className="lp-tool-symbol lp-symbol-research"
                aria-hidden="true"
              >
                ⌕
              </span>
              <div>
                <h3>Get to know the business</h3>
                <p>Explore sample companies and follow the original sources.</p>
              </div>
              <span className="lp-tool-name">Research</span>
              <Arrow />
            </a>
            <a href="./app.html#/what-if" data-lp-arrival>
              <span className="lp-tool-symbol" aria-hidden="true">
                ⇄
              </span>
              <div>
                <h3>Give “what if” a go</h3>
                <p>Change an allocation. Compare the modeled trade-offs.</p>
              </div>
              <span className="lp-tool-name">What-if lab</span>
              <Arrow />
            </a>
          </div>
        </section>
        <section
          className="lp-close"
          data-sc-act="flow"
          aria-labelledby="close-heading"
        >
          <div className="lp-close-inner lp-wrap" data-lp-arrival>
            <div className="lp-close-mark">
              <PandaMark />
            </div>
            <h2 id="close-heading">
              A clearer view
              <br />
              starts with curiosity.
            </h2>
            <DemoLink />
            <p>Explore a sample portfolio. No account needed.</p>
          </div>
          <footer className="lp-footer lp-wrap">
            <a className="lp-brand" href="./">
              <PandaMark />
              <span>Pandaset</span>
            </a>
            <p>
              Built for understanding.
              <br />
              Sample data and modeled results. Not investment advice.
            </p>
            <a href="#main" onClick={goTo("main")}>
              Back to top <span aria-hidden="true">↑</span>
            </a>
          </footer>
        </section>
      </main>
    </div>
  );
}
