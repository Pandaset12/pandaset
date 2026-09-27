import assert from "node:assert/strict";
import { test } from "node:test";
import {
  asAnalysisResponse,
  analysisMatchesPortfolio,
  validPercentAllocation,
  type CaseGrid,
  type ProposedShock,
  type ScenarioDraft,
  type SavedAnalysis,
} from "../src/api/eventLab";
import { assetsForPortfolio } from "../src/types/portfolioAsset";
import {
  contributionSymbols,
  draftAllocationFromSnapshot,
  revisionReviewState,
} from "../src/pages/EventWhatIf";

test("v2 analysis keeps the saved allocation and real-data provenance", () => {
  const saved: SavedAnalysis = {
    analysis_id: "analysis_1",
    portfolio_id: "portfolio_1",
    created_at: "2026-09-26T12:00:00Z",
    metrics: {
      portfolio_id: "portfolio_1",
      data_mode: "live",
      data_as_of: "2026-09-25T20:00:00Z",
      lookback_trading_days: 252,
      portfolio_volatility: 0.21,
      weights: { MSFT: 0.6, IAU: 0.4 },
      portfolio_return: 0.08,
      annualized_return: 0.08,
      max_drawdown: -0.1,
      asset_volatility: null,
      correlation_matrix: null,
      risk_contribution: { MSFT: 0.7, IAU: 0.3 },
      return_contribution: null,
      series: null,
      data_source: "Twelve Data adjusted close",
      freshness: "fresh",
      notes: ["Adjusted close history"],
      assumptions: [],
      observation_count: 252,
      return_frequency: "daily",
      volatility_unit: "annualized_decimal",
    },
  };
  const analysis = asAnalysisResponse(saved);
  assert.deepEqual(analysis.weights, { MSFT: 0.6, IAU: 0.4 });
  assert.deepEqual(analysis.concentration, {
    largest_position: "MSFT",
    largest_weight: 0.6,
  });
  assert.equal(analysis.data_quality.source, "Twelve Data adjusted close");
  assert.equal(analysis.as_of, "2026-09-25T20:00:00Z");
  assert.equal(analysis.data_mode, "live");
  assert.equal(
    analysisMatchesPortfolio(saved, {
      portfolio_id: "portfolio_1",
      name: "My holdings",
      created_at: "now",
      holdings: [
        { symbol: "MSFT", weight: 0.6 },
        { symbol: "IAU", weight: 0.4 },
      ],
    }),
    true,
  );
  assert.equal(
    analysisMatchesPortfolio(saved, {
      portfolio_id: "portfolio_1",
      name: "My holdings",
      created_at: "now",
      holdings: [
        { symbol: "MSFT", weight: 0.5 },
        { symbol: "IAU", weight: 0.5 },
      ],
    }),
    false,
  );
});

test("chat revision opens review state and uses its pinned allocation", () => {
  const proposed_shocks = Object.fromEntries(
    ["mild", "central", "severe"].map((kind) => [
      kind,
      Object.fromEntries(
        ["1m", "3m"].map((horizon) => [
          horizon,
          {
            factors: { equity: -0.02, rates: 0.01, gold: 0.03 },
            issuers: {},
            factor_unit: "cumulative_decimal_return",
            issuer_unit: "residual_sigma_multiple",
            rationale: "Hypothetical",
            evidence_ids: ["source-1"],
          },
        ]),
      ),
    ]),
  ) as CaseGrid<ProposedShock>;
  const revision: ScenarioDraft = {
    draft_id: "draft_2",
    status: "ready",
    revision: 1,
    request: {
      portfolio_id: "portfolio_1",
      analysis_id: "analysis_1",
      template_id: "fed_policy",
      proposed_weights: { MSFT: 0.7, IAU: 0.3 },
    },
    proposal: {
      facts: [{ claim: "New fact", evidence_ids: ["source-1"] }],
      missing_evidence: [],
      evidence: [],
      proposed_shocks,
    },
  };
  const review = revisionReviewState(revision);
  const pinned = draftAllocationFromSnapshot(revision, {
    analysis_id: "analysis_1",
    portfolio_id: "portfolio_1",
    metrics: { weights: { MSFT: 0.6, IAU: 0.4 } },
  } as SavedAnalysis);
  assert.equal(review.run, null);
  assert.equal(review.draft.proposal?.facts[0].claim, "New fact");
  assert.deepEqual(pinned?.current, [60, 40]);
  assert.deepEqual(pinned?.proposed, [70, 30]);
  assert.equal(review.shocks?.central["3m"].factors.equity, -0.02);
});

test("reopened draft uses snapshot symbols after current holdings change", () => {
  const revision: ScenarioDraft = {
    draft_id: "draft_old",
    status: "confirmed",
    revision: 3,
    request: {
      portfolio_id: "portfolio_1",
      analysis_id: "analysis_old",
      template_id: "fed_policy",
    },
    confirmed_shocks: {
      mild: {
        "1m": {
          factors: { equity: -0.01, rates: 0, gold: 0 },
          issuers: { IAU: 0.2 },
        },
        "3m": {
          factors: { equity: -0.01, rates: 0, gold: 0 },
          issuers: { IAU: 0.2 },
        },
      },
      central: {
        "1m": {
          factors: { equity: -0.02, rates: 0, gold: 0 },
          issuers: { IAU: 0.3 },
        },
        "3m": {
          factors: { equity: -0.02, rates: 0, gold: 0 },
          issuers: { IAU: 0.3 },
        },
      },
      severe: {
        "1m": {
          factors: { equity: -0.03, rates: 0, gold: 0 },
          issuers: { IAU: 0.4 },
        },
        "3m": {
          factors: { equity: -0.03, rates: 0, gold: 0 },
          issuers: { IAU: 0.4 },
        },
      },
    },
  };
  const snapshot = {
    analysis_id: "analysis_old",
    portfolio_id: "portfolio_1",
    metrics: { weights: { MSFT: 0.6, IAU: 0.4 } },
  } as SavedAnalysis;
  const pinned = draftAllocationFromSnapshot(revision, snapshot);
  assert.deepEqual(pinned?.symbols, ["MSFT", "IAU"]);
  assert.deepEqual(pinned?.current, [60, 40]);
  assert.deepEqual(pinned?.proposed, [60, 40]);
  assert.equal(
    revisionReviewState(revision).shocks?.central["3m"].issuers.IAU,
    0.3,
  );
  assert.equal(
    draftAllocationFromSnapshot(revision, {
      ...snapshot,
      analysis_id: "another",
    }),
    null,
  );
});

test("saved run contributions retain symbols absent from the current portfolio", () => {
  assert.deepEqual(
    contributionSymbols({ MSFT: 0.03, IAU: 0.01 }, { MSFT: 0.02, IAU: 0.02 }),
    ["MSFT", "IAU"],
  );
  assert.deepEqual(
    contributionSymbols({ MSFT: 0.03 }, { MSFT: 0.02, IAU: 0.02 }),
    ["MSFT", "IAU"],
  );
});

test("saved holdings determine display order without invented research facts", () => {
  const portfolio = {
    portfolio_id: "portfolio_1",
    name: "My holdings",
    created_at: "2026-09-26T12:00:00Z",
    holdings: [
      { symbol: "IAU", weight: 0.4 },
      { symbol: "MSFT", weight: 0.6 },
    ],
  };
  const assets = assetsForPortfolio(portfolio, [
    {
      symbol: "MSFT",
      name: "Microsoft",
      kind: "us_stock",
      sector: "Technology",
    },
  ]);
  assert.deepEqual(
    assets.map((asset) => asset.symbol),
    ["IAU", "MSFT"],
  );
  assert.equal(assets[0].name, "IAU");
  assert.equal(assets[0].sector, null);
  assert.equal(assets[0].source, null);
  assert.equal(assets[1].name, "Microsoft");
  assert.equal(assets[1].thesis, null);
});

test("proposed allocations must reconcile exactly at the displayed precision", () => {
  assert.equal(validPercentAllocation([60, 40]), true);
  assert.equal(validPercentAllocation([33.333333, 33.333333, 33.333334]), true);
  assert.equal(
    validPercentAllocation([33.333333, 33.333333, 33.333333]),
    false,
  );
  assert.equal(validPercentAllocation([100.000001]), false);
  assert.equal(validPercentAllocation([]), false);
});
