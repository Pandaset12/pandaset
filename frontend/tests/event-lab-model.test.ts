import assert from "node:assert/strict";
import { test } from "node:test";
import {
  validPercentAllocation,
  type CaseGrid,
  type ProposedShock,
  type ScenarioDraft,
} from "../src/api/eventLab";
import { proposedShocks, sameWeights } from "../src/components/EventResearch";

test("a saved event draft keeps its exact allocation when the editor changes", () => {
  assert.equal(
    sameWeights({ AAPL: 0.6, TLT: 0.4 }, { TLT: 0.4, AAPL: 0.6 }),
    true,
  );
  assert.equal(sameWeights({ AAPL: 1, TLT: 0 }, { AAPL: 1 }), true);
  assert.equal(
    sameWeights({ AAPL: 0.6, TLT: 0.4 }, { AAPL: 0.5, TLT: 0.5 }),
    false,
  );
  assert.equal(sameWeights({ AAPL: 1 }, { AAPL: 0.6, TLT: 0.4 }), false);
  assert.equal(sameWeights(null, { AAPL: 1 }), false);
});

test("evidence-backed proposed shocks become editable confirmation values", () => {
  const proposed = Object.fromEntries(
    ["mild", "central", "severe"].map((kind) => [
      kind,
      Object.fromEntries(
        ["1m", "3m"].map((horizon) => [
          horizon,
          {
            factors: { equity: -0.02, rates: 0.01, gold: 0.03 },
            issuers: { AAPL: 0.2 },
            factor_unit: "cumulative_decimal_return",
            issuer_unit: "residual_sigma_multiple",
            rationale: "Hypothetical",
            evidence_ids: ["source-1"],
          },
        ]),
      ),
    ]),
  ) as CaseGrid<ProposedShock>;
  const draft: ScenarioDraft = {
    draft_id: "draft-1",
    status: "ready",
    revision: 1,
    portfolio_revision: 2,
    proposed_weights: { AAPL: 0.6, TLT: 0.4 },
    proposal: {
      facts: [],
      evidence: [],
      missing_evidence: [],
      proposed_shocks: proposed,
    },
  };
  const confirmed = proposedShocks(draft);
  assert.deepEqual(confirmed?.central["3m"], {
    factors: { equity: -0.02, rates: 0.01, gold: 0.03 },
    issuers: { AAPL: 0.2 },
  });
  confirmed!.central["3m"].factors.equity = -0.03;
  assert.equal(proposed.central["3m"].factors.equity, -0.02);
});

test("allocation percentages remain exact before event research", () => {
  assert.equal(validPercentAllocation([60, 40]), true);
  assert.equal(validPercentAllocation([33.333333, 33.333333, 33.333334]), true);
  assert.equal(validPercentAllocation([60, 39.9]), false);
});
