import assert from "node:assert/strict";
import { test } from "node:test";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost/",
});
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  MutationObserver: dom.window.MutationObserver,
});

const { createElement } = await import("react");
const { cleanup, fireEvent, render, screen } =
  await import("@testing-library/react");
const { EventResearch, eventResearchApi } =
  await import("../src/components/EventResearch");
const originalCrypto = globalThis.crypto;
Object.defineProperty(globalThis, "crypto", {
  value: { randomUUID: () => "request-1" },
  configurable: true,
});

test("event research reviews saved evidence and refuses stale confirmation", async () => {
  const calls: string[] = [];
  const shocks = Object.fromEntries(
    ["mild", "central", "severe"].map((kind) => [
      kind,
      Object.fromEntries(
        ["1m", "3m"].map((horizon) => [
          horizon,
          {
            factors: { equity: 0.01, rates: -0.01, gold: 0 },
            issuers: {},
            factor_unit: "cumulative_decimal_return",
            issuer_unit: "residual_sigma_multiple",
            rationale: "Hypothetical",
            evidence_ids: ["source-1"],
          },
        ]),
      ),
    ]),
  );
  const draft = {
    draft_id: "draft-1",
    status: "ready",
    revision: 1,
    portfolio_revision: 2,
    proposed_weights: { SPY: 1 },
    allocation_snapshot: { name: "Core" },
    price_window: { start: "2025-01-01", end: "2025-12-31" },
    proposal: {
      scenario_brief: "Rates fall sooner",
      facts: [{ claim: "Policy rate recorded", evidence_ids: ["source-1"] }],
      missing_evidence: ["Forward guidance"],
      evidence: [
        {
          evidence_id: "source-1",
          title: "Federal Reserve",
          status: "available",
          source_url: "https://www.federalreserve.gov/",
        },
      ],
      proposed_shocks: shocks,
    },
  };
  const api = {
    ...eventResearchApi,
    listTemplates: async () => [
      {
        template_id: "fed_policy",
        version: "1",
        category: "macro",
        title: "Federal Reserve policy decision",
        description: "",
        factor_ids: ["equity", "rates", "gold"],
        situations: [
          {
            situation_id: "faster_cuts",
            title: "Rates fall sooner",
            description: "",
          },
        ],
      },
    ],
    listDrafts: async () => [],
    listRuns: async () => [],
    createDraft: async (body: { portfolio_revision?: number }) => {
      calls.push(`create:${body.portfolio_revision}`);
      return { draft_id: "draft-1", status: "pending" };
    },
    getDraft: async () => draft,
    confirmDraft: async () => {
      calls.push("confirm");
      return { run_id: "run-1", status: "pending" };
    },
  } as unknown as typeof eventResearchApi;
  const props = {
    portfolioId: "portfolio-1",
    portfolioRevision: 2,
    proposedWeights: { SPY: 1 },
    validAllocation: true,
    api,
  };
  const view = render(createElement(EventResearch, props));
  try {
    await screen.findByRole("combobox", { name: "Situation" });
    const eventSelect = screen.getByRole("combobox", { name: "Event" });
    eventSelect.focus();
    assert.equal(document.activeElement, eventSelect);
    fireEvent.change(screen.getByRole("combobox", { name: "Situation" }), {
      target: { value: "faster_cuts" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Research this event" }),
    );
    await screen.findByText("Policy rate recorded");
    assert.match(
      screen.getByText(/Missing evidence:/).textContent ?? "",
      /Forward guidance/,
    );
    assert.match(
      screen.getByText(/Pinned to Core/).textContent ?? "",
      /revision 2/,
    );
    assert.equal(
      screen
        .getByRole("button", { name: "Confirm assumptions and calculate" })
        .hasAttribute("disabled"),
      false,
    );
    const shockInput = screen.getAllByRole("spinbutton", {
      name: /equity · %/,
    })[0];
    shockInput.focus();
    assert.equal(document.activeElement, shockInput);
    view.rerender(
      createElement(EventResearch, {
        ...props,
        proposedWeights: { SPY: 0.8, AAPL: 0.2 },
      }),
    );
    await screen.findByText(/proposed allocation or portfolio changed/);
    assert.equal(
      screen
        .getByRole("button", { name: "Confirm assumptions and calculate" })
        .hasAttribute("disabled"),
      true,
    );
    assert.deepEqual(calls, ["create:2"]);
  } finally {
    view.unmount();
    cleanup();
    Object.defineProperty(globalThis, "crypto", {
      value: originalCrypto,
      configurable: true,
    });
  }
});

test("event outage keeps allocation comparison available and offers retry", async () => {
  const api = {
    ...eventResearchApi,
    listTemplates: async () => {
      throw new Error("Service down");
    },
  } as typeof eventResearchApi;
  const view = render(
    createElement(EventResearch, {
      portfolioId: "portfolio-2",
      portfolioRevision: 1,
      proposedWeights: { SPY: 1 },
      validAllocation: true,
      api,
    }),
  );
  try {
    await screen.findByText("Event research is unavailable right now.");
    assert.match(
      screen.getByText(/compare and apply allocations/).textContent ?? "",
      /compare and apply/,
    );
    assert.ok(screen.getByRole("button", { name: "Try event research again" }));
  } finally {
    view.unmount();
    cleanup();
  }
});

test("event access denial stays inside the optional panel", async () => {
  const api = {
    ...eventResearchApi,
    listTemplates: async () => {
      throw new Error("The event lab is not available to this account.");
    },
  } as typeof eventResearchApi;
  const view = render(
    createElement(EventResearch, {
      portfolioId: "portfolio-3",
      portfolioRevision: 1,
      proposedWeights: { SPY: 1 },
      validAllocation: true,
      api,
    }),
  );
  try {
    await screen.findByText("The event lab is not available to this account.");
    assert.ok(
      screen.getByRole("heading", { name: "Add an event to this scenario" }),
    );
    assert.ok(screen.getByText(/compare and apply allocations above/));
  } finally {
    view.unmount();
    cleanup();
  }
});

test("a saved-run revision opens its new pinned draft for review", async () => {
  const confirmations: string[] = [];
  const savedRun = {
    run_id: "run-1",
    status: "completed",
    created_at: "2026-09-27T00:00:00Z",
    portfolio_revision: 1,
    allocation_snapshot: { name: "Original" },
    proposed_weights: { SPY: 1 },
    result: {
      cases: [],
      probabilities: { status: "omitted", reason: "uncalibrated", central: {} },
      model_version: "event-v1",
    },
  };
  const revisedDraft = {
    draft_id: "draft-revised",
    status: "ready",
    revision: 1,
    portfolio_revision: 1,
    proposed_weights: { SPY: 1 },
    request: { source_run_id: "run-1" },
    proposal: {
      scenario_brief: "Revised assumptions",
      facts: [],
      missing_evidence: [],
      evidence: [],
      proposed_shocks: Object.fromEntries(
        ["mild", "central", "severe"].map((kind) => [
          kind,
          Object.fromEntries(
            ["1m", "3m"].map((horizon) => [
              horizon,
              {
                factors: { equity: 0, rates: 0, gold: 0 },
                issuers: {},
              },
            ]),
          ),
        ]),
      ),
    },
  };
  const api = {
    ...eventResearchApi,
    listTemplates: async () => [],
    listDrafts: async () => [],
    listRuns: async () => [savedRun],
    getDraft: async () => revisedDraft,
    confirmDraft: async () => {
      confirmations.push("confirmed");
      return { run_id: "run-revised", status: "pending" };
    },
    getRun: async () => ({ ...savedRun, run_id: "run-revised" }),
    sendMessage: async () => ({
      revision_draft_id: "draft-revised",
      message: {
        message: {
          answer: "A new draft is ready for review before recalculation.",
          revision_draft_id: "draft-revised",
        },
      },
    }),
  } as unknown as typeof eventResearchApi;
  const view = render(
    createElement(EventResearch, {
      portfolioId: "portfolio-4",
      portfolioRevision: 2,
      proposedWeights: { SPY: 1 },
      validAllocation: true,
      api,
    }),
  );
  try {
    fireEvent.click(await screen.findByText("Saved event research and runs"));
    fireEvent.click(await screen.findByRole("button", { name: /completed/ }));
    fireEvent.change(
      screen.getByRole("textbox", { name: "Ask about this result" }),
      {
        target: { value: "Change the shock assumptions" },
      },
    );
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await screen.findByText("Revised assumptions");
    assert.ok(screen.getByText(/uses the saved run’s portfolio allocation/));
    assert.equal(
      screen.queryByText(/proposed allocation or portfolio changed/),
      null,
    );
    const confirmButton = screen.getByRole("button", {
      name: "Confirm assumptions and calculate",
    });
    assert.equal(confirmButton.hasAttribute("disabled"), false);
    fireEvent.click(confirmButton);
    await screen.findByText("Event-conditioned results");
    assert.deepEqual(confirmations, ["confirmed"]);
  } finally {
    view.unmount();
    cleanup();
  }
});
